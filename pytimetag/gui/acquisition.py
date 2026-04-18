from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Union

import duckdb

from pytimetag.analysers.CounterAnalyser import CounterAnalyser
from pytimetag.analysers.HistogramAnalyser import HistogramAnalyser
from pytimetag.datablock import DataBlock
from pytimetag.device.Simulator import unpack_timetag
from pytimetag.device.datablock_packer import (
    DataBlockPackerPath,
    DataBlockStreamPacker,
    SplitByChannelEvent,
    SplitByTimeWindow,
)
from pytimetag.gui.config import StreamPathConfig
from pytimetag.storage import Storage


class AcquisitionService:
    def __init__(
        self,
        stream_paths: List[StreamPathConfig],
        channel_count: int,
        resolution: float,
        split: Union[SplitByTimeWindow, SplitByChannelEvent],
        metrics_cb: Callable[[Dict[str, Any]], None],
        log_cb: Callable[[str, str], None],
        save_raw_data: bool = False,
    ) -> None:
        self._stream_paths = stream_paths
        self._channel_count = channel_count
        self._resolution = resolution
        self._split = split
        self._metrics_cb = metrics_cb
        self._log_cb = log_cb
        self._save_raw_data = save_raw_data
        self._lock = Lock()
        self._running = False
        self._started_at = 0.0
        self._events_total = 0
        self._blocks = 0
        self._last_analyser: Dict[str, Any] = {}
        self._rate_inst = 0
        self._recent_rates = deque(maxlen=5)
        self._packer = DataBlockStreamPacker(
            [
                DataBlockPackerPath(cfg.name, split, channel_count=16, resolution=resolution)
                for cfg in stream_paths
            ]
        )
        self._paths: Dict[str, Dict[str, Any]] = {}
        for cfg in stream_paths:
            db_path = Path(cfg.storage_db).resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = duckdb.connect(str(db_path))
            self._paths[cfg.name] = {
                "storage_db": db_path,
                "datablock_dir": Path(cfg.datablock_dir).resolve(),
                "conn": conn,
                "storage": Storage(conn, timezone="utc"),
            }
        self._counter = CounterAnalyser()
        self._counter.turnOn()
        self._hist = HistogramAnalyser(channel_count)
        self._hist.turnOn(
            {
                "Sync": 0,
                "Signals": list(range(1, min(channel_count, 16))),
                "ViewStart": -100000,
                "ViewStop": 100000,
                "BinCount": 1000,
                "Divide": 1,
            }
        )
        self._hist_last_error = ""
        self._rate_history: deque[Dict[str, Any]] = deque(maxlen=200)
        self._last_block_time: Optional[float] = None
        self._block_intervals: deque[float] = deque(maxlen=100)

    @property
    def default_path_name(self) -> str:
        return self._stream_paths[0].name if self._stream_paths else "default"

    def get_block_interval_stats(self) -> Dict[str, Any]:
        with self._lock:
            intervals = list(self._block_intervals)
            last = self._last_block_time
        n = len(intervals)
        if n == 0:
            return {"count": 0, "mean": 0, "std": 0, "min": 0, "max": 0, "last": 0}
        mean = sum(intervals) / n
        variance = sum((x - mean) ** 2 for x in intervals) / n
        return {
            "count": n,
            "mean": mean,
            "std": variance ** 0.5,
            "min": min(intervals),
            "max": max(intervals),
            "last": intervals[-1] if intervals else 0,
        }

    def get_storage(self, name: Optional[str] = None) -> Storage:
        if name is None:
            name = self.default_path_name
        try:
            return self._paths[name]["storage"]
        except KeyError as exc:
            raise ValueError(f"Unknown stream path: {name}") from exc

    def _ensure_output_path(self, block: DataBlock, base_dir: Path) -> Path:
        dt = datetime.fromtimestamp(block.creationTime / 1000.0, tz=timezone.utc)
        day = dt.strftime("%Y-%m-%d")
        hour = dt.strftime("%H")
        save_dir = base_dir / day / hour
        save_dir.mkdir(parents=True, exist_ok=True)
        filename = dt.strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3] + ".datablock"
        return save_dir / filename

    def _persist_analysers(self, storage: Storage, block: DataBlock, rows: List[tuple[str, dict]]) -> None:
        if not rows:
            return
        fetch_time = datetime.now(tz=timezone.utc).isoformat()

        async def _persist() -> None:
            for name, doc in rows:
                await storage.append(name, doc, fetch_time)

        try:
            asyncio.run(_persist())
        except BaseException as exc:
            self._log_cb("error", f"persist failed: {exc}")

    def get_rate_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            history = list(self._rate_history)
        items = history[-limit:] if limit < len(history) else history
        result = []
        prev_time = None
        for item in items:
            t = datetime.fromisoformat(item["FetchTime"])
            if prev_time is None:
                prev_time = t
                continue
            dt = (t - prev_time).total_seconds()
            counts = item["Data"]
            rates = []
            for ch in range(self._channel_count):
                c = counts.get(str(ch), 0)
                rates.append(round(c / dt) if dt > 0 else 0)
            result.append({"time": int(t.timestamp() * 1000), "rates": rates})
            prev_time = t
        return result

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
                    span_s = span_ticks * self._resolution
                    chunk_rate = int(len(words) / span_s)
                    with self._lock:
                        self._rate_inst = max(0, chunk_rate)
            except BaseException:
                pass

        produced = self._packer.feed_from_packed(words)
        for path_name, blocks in produced.items():
            path_cfg = self._paths[path_name]
            for block in blocks:
                if self._save_raw_data:
                    payload = block.serialize()
                    out = self._ensure_output_path(block, path_cfg["datablock_dir"])
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
                self._persist_analysers(path_cfg["storage"], block, analyser_rows)
                fetch_time_iso = datetime.now(tz=timezone.utc).isoformat()
                now = time.time()
                with self._lock:
                    block_events = int(sum(block.sizes))
                    self._events_total += block_events
                    self._blocks += 1
                    block_duration_s = max((block.dataTimeEnd - block.dataTimeBegin) * block.resolution, 1e-9)
                    block_rate = int(block_events / block_duration_s)
                    self._recent_rates.append(block_rate)
                    self._rate_history.append({
                        "FetchTime": fetch_time_iso,
                        "Data": {k: v for k, v in counter_res.items() if k != "Configuration"},
                    })
                    if self._last_block_time is not None:
                        interval = (now - self._last_block_time) * 1000.0
                        self._block_intervals.append(interval)
                    self._last_block_time = now
                self._last_analyser = {
                    "CounterAnalyser": counter_res,
                    "HistogramAnalyser": hist_res,
                }
                self._metrics_cb(self.snapshot_metrics())

    def start(self) -> Dict[str, Any]:
        with self._lock:
            if self._running:
                return self.snapshot_metrics()
            self._running = True
            self._started_at = time.time()
            self._events_total = 0
            self._blocks = 0
            self._last_analyser = {}
            self._rate_inst = 0
            self._recent_rates.clear()
        self._log_cb("info", "Acquisition started")
        return self.snapshot_metrics()

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._running = False
        tail = self._packer.flush()
        if self._save_raw_data:
            for path_name, blocks in tail.items():
                path_cfg = self._paths.get(path_name)
                if path_cfg is None:
                    continue
                for block in blocks:
                    out = self._ensure_output_path(block, path_cfg["datablock_dir"])
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
                "blocks": self._blocks,
                "events_total": self._events_total,
                "events_rate_per_s": self._rate_inst,
                "events_rate_avg_per_s": rate_avg,
                "uptime_s": uptime,
                "last_analyser": self._last_analyser,
            }
