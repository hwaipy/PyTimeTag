import argparse
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from pytimetag.device.Simulator import TimeTagSimulator, unpack_timetag
import pytimetag.device.datablock_packer as dbp
from pytimetag.device.datablock_packer import DataBlockPackerPath, DataBlockStreamPacker, SplitByTimeWindow


@dataclass
class StepData:
    words: np.ndarray
    timestamps: np.ndarray
    channels: np.ndarray
    span_s: float


class TimedPacker(DataBlockStreamPacker):
    def __init__(self, paths):
        super().__init__(paths)
        self.stats: Dict[str, float] = {
            "feed_total_s": 0.0,
            "cast_s": 0.0,
            "filter_s": 0.0,
            "process_lane_s": 0.0,
            "append_s": 0.0,
            "emit_block_s": 0.0,
            "pack_content_s": 0.0,
            "create_block_s": 0.0,
            "searchsorted_s": 0.0,
            "unpack_s": 0.0,
        }
        self.counts: Dict[str, int] = {
            "feed_calls": 0,
            "feed_from_packed_calls": 0,
            "append_calls": 0,
            "emit_calls": 0,
            "blocks_emitted": 0,
            "searchsorted_calls": 0,
        }

    def _append(self, ln, ts, ch):
        t0 = time.perf_counter()
        out = super()._append(ln, ts, ch)
        self.stats["append_s"] += (time.perf_counter() - t0)
        self.counts["append_calls"] += 1
        return out

    def _emit_block(self, ln, ts, ch, creation_ms):
        t0 = time.perf_counter()
        content = dbp._pack_flat_to_content(ts, ch)
        t1 = time.perf_counter()
        self.stats["pack_content_s"] += (t1 - t0)
        b0 = time.perf_counter()
        t0i = int(np.int64(ts[0]))
        t1i = int(np.int64(ts[-1]))
        block = dbp.DataBlock.create(content, creation_ms, t0i, t1i, resolution=ln.cfg.resolution)
        self.stats["create_block_s"] += (time.perf_counter() - b0)
        self.stats["emit_block_s"] += (time.perf_counter() - t0)
        self.counts["emit_calls"] += 1
        self.counts["blocks_emitted"] += 1
        return block

    def _process_lane(self, ln, ts, ch, creation_ms):
        t0 = time.perf_counter()
        out = super()._process_lane(ln, ts, ch, creation_ms)
        self.stats["process_lane_s"] += (time.perf_counter() - t0)
        return out

    def feed(self, timestamps: np.ndarray, channels: np.ndarray):
        all_t0 = time.perf_counter()
        t0 = time.perf_counter()
        ts = np.ascontiguousarray(timestamps, dtype=np.int64)
        ch = np.ascontiguousarray(channels, dtype=np.int64)
        self.stats["cast_s"] += (time.perf_counter() - t0)
        if ts.shape != ch.shape:
            raise ValueError("timestamps and channels must have the same shape")
        creation_ms = time.time_ns() / 1e6
        result = {}
        for ln in self._lanes:
            if ln.skip_channel_filter:
                ft, fc = ts, ch
            else:
                f0 = time.perf_counter()
                ft, fc = dbp._filter_by_channel_mask(ts, ch, ln.mask)
                self.stats["filter_s"] += (time.perf_counter() - f0)
            blocks = self._process_lane(ln, ft, fc, creation_ms)
            if blocks:
                result[ln.cfg.name] = blocks
        self.stats["feed_total_s"] += (time.perf_counter() - all_t0)
        self.counts["feed_calls"] += 1
        return result

    def feed_from_packed(self, words: np.ndarray):
        t0 = time.perf_counter()
        out = super().feed_from_packed(words)
        self.stats["unpack_s"] += (time.perf_counter() - t0)
        self.counts["feed_from_packed_calls"] += 1
        return out

    def reset_timing_stats(self):
        for k in self.stats:
            self.stats[k] = 0.0
        for k in self.counts:
            self.counts[k] = 0


def _run_once(packer: TimedPacker, steps: List[StepData]):
    """Run one full pass (same flow as measured run): reset -> feed all steps -> flush."""
    packer.reset()
    for s in steps:
        packer.feed(s.timestamps, s.channels)
    return packer.flush()


def _patch_searchsorted_timing(packer: TimedPacker):
    orig_searchsorted = np.searchsorted

    def timed_searchsorted(*args, **kwargs):
        t0 = time.perf_counter()
        v = orig_searchsorted(*args, **kwargs)
        packer.stats["searchsorted_s"] += (time.perf_counter() - t0)
        packer.counts["searchsorted_calls"] += 1
        return v

    return orig_searchsorted, timed_searchsorted


def prepare_steps(
    duration_s: float,
    target_events_total: int,
    step_lo_s: float,
    step_hi_s: float,
    seed: int,
) -> Tuple[List[StepData], float, int]:
    steps: List[StepData] = []
    sim_cursor_s = [0.0]
    total_events = [0]

    # Total target ~25M for 4 signal channels + sparse ch0 PPS.
    signal_rate_hz = max(1, int(round(target_events_total / duration_s / 4.0)))

    def on_words(words: np.ndarray):
        ts, ch = unpack_timetag(words)
        if ts.size > 0:
            span_s = (int(ts[-1]) - int(ts[0])) * 1e-12
            total_events[0] += int(ts.size)
        else:
            span_s = 0.0
        steps.append(StepData(words=words.copy(), timestamps=ts, channels=ch, span_s=span_s))

    sim = TimeTagSimulator(
        on_words,
        channel_count=5,
        seed=seed,
        resolution=1e-12,
        update_interval_range_s=(step_lo_s, step_hi_s),
        realtime_pacing=False,
    )
    sim.set_channel(0, mode="Period", period_count=1, threshold_voltage=-1.0, reference_pulse_v=1.0)
    for i in range(1, 5):
        sim.set_channel(i, mode="Random", random_count=signal_rate_hz, threshold_voltage=-1.0, reference_pulse_v=1.0)

    while sim._cursor * sim.resolution < duration_s:
        before = sim._cursor
        sim.step()
        after = sim._cursor
        sim_cursor_s[0] += (after - before) * sim.resolution

    return steps, sim_cursor_s[0], total_events[0]


def fmt_ms(x_s: float) -> str:
    return f"{x_s * 1000.0:,.3f} ms"


def fmt_pct(part: float, total: float) -> str:
    if total <= 0:
        return "0.0%"
    return f"{(part / total) * 100.0:.1f}%"


def main():
    parser = argparse.ArgumentParser(
        description="Standalone packer timing probe: prepare simulator data, then feed TW1s packer and report step timings."
    )
    parser.add_argument("--duration-s", type=float, default=2.5, help="Simulated timeline seconds to prepare")
    parser.add_argument("--target-events", type=int, default=25_000_000, help="Approx total events to generate")
    parser.add_argument("--step-lo-s", type=float, default=0.05, help="Simulator step lower bound (s)")
    parser.add_argument("--step-hi-s", type=float, default=0.1, help="Simulator step upper bound (s)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    t0 = time.perf_counter()
    steps, prepared_span_s, total_events = prepare_steps(
        args.duration_s, args.target_events, args.step_lo_s, args.step_hi_s, args.seed
    )
    prep_s = time.perf_counter() - t0

    packer = TimedPacker([DataBlockPackerPath("w", SplitByTimeWindow(int(round(1.0 / 1e-12))))])

    # Full warmup pass with the exact same data and control flow, outside measured region.
    if steps:
        _run_once(packer, steps)
        packer.reset()
        packer.reset_timing_stats()

    original_searchsorted, timed_searchsorted = _patch_searchsorted_timing(packer)
    np.searchsorted = timed_searchsorted
    try:
        run_t0 = time.perf_counter()
        flush_out = _run_once(packer, steps)
        run_s = time.perf_counter() - run_t0
    finally:
        np.searchsorted = original_searchsorted

    emitted = sum(len(v) for v in flush_out.values()) + packer.counts["blocks_emitted"]
    ev_per_s = total_events / max(prepared_span_s, 1e-12)

    print("\n=== Dataset Prepared ===")
    print(f"steps: {len(steps)}")
    print(f"prepared timeline: {prepared_span_s:.6f} s")
    print(f"total events: {total_events:,}")
    print(f"events/s: {ev_per_s:,.2f}")
    print(f"prepare time (simulator+decode): {prep_s:.6f} s")

    print("\n=== Packer Run (TW1s) ===")
    print(f"feed calls: {packer.counts['feed_calls']}")
    print(f"blocks emitted (including flush): {emitted}")
    print(f"total packer wall time: {run_s:.6f} s")
    print(f"ms per simulated second: {(run_s * 1000.0) / max(prepared_span_s, 1e-12):.3f} ms/s")

    print("\n=== Internal Timing Breakdown ===")
    s = packer.stats
    print(f"feed_total_s      {fmt_ms(s['feed_total_s']):>14}   {fmt_pct(s['feed_total_s'], run_s):>6}")
    print(f"cast_s            {fmt_ms(s['cast_s']):>14}   {fmt_pct(s['cast_s'], run_s):>6}")
    print(f"filter_s          {fmt_ms(s['filter_s']):>14}   {fmt_pct(s['filter_s'], run_s):>6}")
    print(f"process_lane_s    {fmt_ms(s['process_lane_s']):>14}   {fmt_pct(s['process_lane_s'], run_s):>6}")
    print(f"append_s          {fmt_ms(s['append_s']):>14}   {fmt_pct(s['append_s'], run_s):>6}")
    print(f"emit_block_s      {fmt_ms(s['emit_block_s']):>14}   {fmt_pct(s['emit_block_s'], run_s):>6}")
    print(f"pack_content_s    {fmt_ms(s['pack_content_s']):>14}   {fmt_pct(s['pack_content_s'], run_s):>6}")
    print(f"create_block_s    {fmt_ms(s['create_block_s']):>14}   {fmt_pct(s['create_block_s'], run_s):>6}")
    print(f"searchsorted_s    {fmt_ms(s['searchsorted_s']):>14}   {fmt_pct(s['searchsorted_s'], run_s):>6}")
    print(f"unpack_s          {fmt_ms(s['unpack_s']):>14}   {fmt_pct(s['unpack_s'], run_s):>6}")

    print("\n=== Counts ===")
    for k in ("append_calls", "emit_calls", "blocks_emitted", "searchsorted_calls"):
        print(f"{k:17s} {packer.counts[k]:,}")


if __name__ == "__main__":
    main()
