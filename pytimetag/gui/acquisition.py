from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

import duckdb

from pytimetag.analysers.CounterAnalyser import CounterAnalyser
from pytimetag.analysers.HistogramAnalyser import HistogramAnalyser
from pytimetag.datablock import DataBlock
from pytimetag.device import TimeTagSimulator
from pytimetag.device.Simulator import unpack_timetag
from pytimetag.device.datablock_packer import DataBlockPackerPath, DataBlockStreamPacker, SplitByTimeWindow
from pytimetag.storage import Storage


class AcquisitionService:
    def __init__(
        self,
        storage_db: Path,
        datablock_dir: Path,
        metrics_cb: Callable[[Dict[str, Any]], None],
        log_cb: Callable[[str, str], None],
    ) -> None:
        self._storage_db = storage_db
        self._datablock_dir = datablock_dir
        self._metrics_cb = metrics_cb
        self._log_cb = log_cb
        self._lock = Lock()
        self._running = False
        self._source = "simulator"
        self._started_at = 0.0
        self._events_total = 0
        self._blocks = 0
        self._last_analyser: Dict[str, Any] = {}
        self._rate_inst = 0
        self._recent_rates = deque(maxlen=5)
        self._simulator: Optional[TimeTagSimulator] = None
        self._packer = DataBlockStreamPacker(
            [DataBlockPackerPath("stream", SplitByTimeWindow(int(1e12)), channel_count=16, resolution=1e-12)]
        )
        self._conn = duckdb.connect(str(storage_db))
        self._storage = Storage(self._conn, timezone="utc")
        self._counter = CounterAnalyser()
        self._counter.turnOn()
        self._hist = HistogramAnalyser(8)
        self._hist.turnOff()
        self._hist_last_error = ""

    def _ensure_output_path(self, block: DataBlock) -> Path:
        dt = datetime.fromtimestamp(block.creationTime / 1000.0, tz=timezone.utc)
        day = dt.strftime("%Y-%m-%d")
        hour = dt.strftime("%H")
        save_dir = self._datablock_dir / day / hour
        save_dir.mkdir(parents=True, exist_ok=True)
        filename = dt.strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3] + ".datablock"
        return save_dir / filename

    def _persist_analysers(self, block: DataBlock, rows: List[tuple[str, dict]]) -> None:
        if not rows:
            return
        end_s = block.dataTimeEnd * block.resolution
        fetch_time = datetime.fromtimestamp(end_s, tz=timezone.utc).isoformat()

        async def _persist() -> None:
            for name, doc in rows:
                await self._storage.append(name, doc, fetch_time)

        asyncio.run(_persist())

    def analyser_status(self) -> Dict[str, Any]:
        return {
            "CounterAnalyser": {
                "enabled": self._counter.isTurnedOn(),
                "configuration": self._counter.getConfigurations(),
            },
            "HistogramAnalyser": {
                "enabled": self._hist.isTurnedOn(),
                "configuration": self._hist.getConfigurations(),
                "last_error": self._hist_last_error,
            },
        }

    def configure_analyser(self, name: str, enabled: bool, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if name == "CounterAnalyser":
            if enabled:
                self._counter.turnOn(config or {})
            else:
                self._counter.turnOff()
            return self.analyser_status()[name]
        if name == "HistogramAnalyser":
            if enabled:
                self._hist.turnOn(config or {})
            else:
                self._hist.turnOff()
            self._hist_last_error = ""
            return self.analyser_status()[name]
        raise ValueError(f"Unknown analyser: {name}")

    def _on_words(self, words) -> None:
        # Instantaneous rate from simulator callback chunk (typically 50~100 ms).
        if words is not None and len(words) > 1:
            try:
                ts, _ = unpack_timetag(words)
                span_ticks = int(ts[-1]) - int(ts[0])
                if span_ticks > 0:
                    span_s = span_ticks * 1e-12
                    chunk_rate = int(len(words) / span_s)
                    with self._lock:
                        self._rate_inst = max(0, chunk_rate)
            except BaseException:
                pass

        produced = self._packer.feed_from_packed(words)
        for _, blocks in produced.items():
            for block in blocks:
                payload = block.serialize()
                out = self._ensure_output_path(block)
                out.write_bytes(payload)
                analyser_rows: List[tuple[str, dict]] = []
                counter_res = self._counter.dataIncome(block)
                analyser_rows.append(("CounterAnalyser", counter_res))
                hist_res: Dict[str, Any] = {}
                if self._hist.isTurnedOn():
                    try:
                        hist_res = self._hist.dataIncome(block)
                        analyser_rows.append(("HistogramAnalyser", hist_res))
                        self._hist_last_error = ""
                    except BaseException as exc:
                        self._hist_last_error = str(exc)
                        self._log_cb("error", f"HistogramAnalyser failed: {exc}")
                self._last_analyser = {
                    "CounterAnalyser": counter_res,
                    "HistogramAnalyser": hist_res,
                }
                self._persist_analysers(block, analyser_rows)
                with self._lock:
                    block_events = int(sum(block.sizes))
                    self._events_total += block_events
                    self._blocks += 1
                    block_duration_s = max((block.dataTimeEnd - block.dataTimeBegin) * block.resolution, 1e-9)
                    block_rate = int(block_events / block_duration_s)
                    self._recent_rates.append(block_rate)
                self._metrics_cb(self.snapshot_metrics())

    def start(self, source: str = "simulator") -> Dict[str, Any]:
        with self._lock:
            if self._running:
                return self.snapshot_metrics()
            self._running = True
            self._source = source
            self._started_at = time.time()
            self._events_total = 0
            self._blocks = 0
            self._last_analyser = {}
            self._rate_inst = 0
            self._recent_rates.clear()
        self._simulator = TimeTagSimulator(
            dataUpdate=self._on_words,
            channel_count=8,
            resolution=1e-12,
            seed=42,
            update_interval_range_s=(0.05, 0.10),
            realtime_pacing=True,
        )
        self._simulator.set_channel(0, mode="Period", period_count=5_000, threshold_voltage=-1.0, reference_pulse_v=1.0)
        for i in range(1, 8):
            self._simulator.set_channel(i, mode="Random", random_count=50_000, threshold_voltage=-1.0, reference_pulse_v=1.0)
        self._simulator.start()
        self._log_cb("info", f"Acquisition started ({source})")
        return self.snapshot_metrics()

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._running = False
        if self._simulator is not None:
            self._simulator.stop()
            self._simulator = None
        tail = self._packer.flush()
        for _, blocks in tail.items():
            for block in blocks:
                out = self._ensure_output_path(block)
                out.write_bytes(block.serialize())
        self._log_cb("info", "Acquisition stopped")
        return self.snapshot_metrics()

    def snapshot_metrics(self) -> Dict[str, Any]:
        with self._lock:
            uptime = max(0.0, time.time() - self._started_at) if self._running else 0.0
            if not self._running:
                self._rate_inst = 0
            rate_avg = int(self._events_total / max(uptime, 1.0)) if self._running else 0
            return {
                "running": self._running,
                "source": self._source,
                "blocks": self._blocks,
                "events_total": self._events_total,
                "events_rate_per_s": self._rate_inst,
                "events_rate_avg_per_s": rate_avg,
                "uptime_s": uptime,
                "last_analyser": self._last_analyser,
            }

