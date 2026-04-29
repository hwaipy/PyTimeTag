__license__ = "GNU General Public License v3"
__author__ = 'Hwaipy'
__email__ = 'hwaipy@gmail.com'

import math
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple, Union

import numpy as np
from pytimetag.device.base import TimeTagDevice

DEFAULT_CHANNEL_COUNT = 16
MAX_PACKED_CHANNELS = 16


def pack_timetag(time_ticks: np.ndarray, channels: np.ndarray) -> np.ndarray:
    """
    Pack timetags into ``uint64`` words (vectorized NumPy): upper bits = time tick, low 4 bits = channel.

    ``time_ticks`` and ``channels`` must be :class:`numpy.ndarray` only (no scalars or Python lists).
    They must have the **same shape**. ``channels`` values must lie in ``0..15``.
    Returns a **new** ``uint64`` array of that shape.

    Time ticks use the same unit as :class:`DataBlock` (one tick = ``resolution`` seconds in the
    simulator; default resolution ``1e-12`` ⇒ picoseconds per tick).
    """
    if not isinstance(time_ticks, np.ndarray):
        raise TypeError('time_ticks must be a numpy.ndarray, got {!r}'.format(type(time_ticks).__name__))
    if not isinstance(channels, np.ndarray):
        raise TypeError('channels must be a numpy.ndarray, got {!r}'.format(type(channels).__name__))
    if time_ticks.shape != channels.shape:
        raise ValueError(
            'time_ticks and channels must have the same shape (length / size), got {!r} and {!r}'.format(
                time_ticks.shape,
                channels.shape,
            )
        )
    tt = np.ascontiguousarray(time_ticks, dtype=np.int64)
    ch = np.ascontiguousarray(channels, dtype=np.int64)
    if ch.size and (ch.min() < 0 or ch.max() > 0xF):
        raise ValueError('channel must be in 0..15 for 4-bit packing')
    tu = tt.view(np.uint64)
    return (tu << np.uint64(4)) | (ch.astype(np.uint64) & np.uint64(15))


def unpack_timetag(words: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Unpack ``uint64`` timetag words in batch (vectorized NumPy). ``words`` must be a
    :class:`numpy.ndarray` only. Returns ``(time_ticks, channels)`` as **new** ``int64`` arrays with
    the same shape as ``words``.
    """
    if not isinstance(words, np.ndarray):
        raise TypeError('words must be a numpy.ndarray, got {!r}'.format(type(words).__name__))
    w = words.astype(np.uint64, copy=False)
    t_u = w >> np.uint64(4)
    times = t_u.view(np.int64).copy()
    channels = (w & np.uint64(15)).astype(np.int64, copy=True)
    return times, channels


@dataclass
class ChannelSettings:
    """
    Per-channel simulation parameters.

    ``mode`` is one of ``None`` (off), ``'Period'``, ``'Random'``, ``'RandomPulse'`` (alias ``'Pulse'``).

    **Public time quantities are in seconds** (together with :attr:`TimeTagSimulator.resolution` as
    seconds per tick); synthesis uses integer **ticks** internally.

    In :class:`TimeTagSimulator`, ``period_count`` and ``random_count`` are **rates in Hz**
    (events per second of lab time). Each batch uses ``round(rate * Δt)`` events, where ``Δt`` is
    the simulated window width in seconds. ``Period`` places events on a **global** grid
    ``…, 0, P, 2P, …`` ticks so timing stays coherent across batches. ``Pulse`` mode treats
    ``pulse_count`` / ``pulse_events`` as **rates in Hz** and uses a global pulse train (fixed phase
    across batches) plus optional Gaussian jitter.
    ``pulse_sigma_s`` is the Gaussian jitter standard deviation in **seconds** (converted to ticks
    via ``sigma_ticks = pulse_sigma_s / resolution``).
    """

    mode: Optional[str] = None
    period_count: int = 0
    random_count: int = 0
    pulse_count: int = 0
    pulse_events: int = 0
    pulse_sigma_s: float = 0.0
    dead_time_s: float = 0.0
    threshold_voltage: float = 0.0
    reference_pulse_v: float = 0.8
    enabled: bool = True

    def to_generate_tuple(self, resolution: Optional[float] = None) -> Optional[Tuple]:
        """
        Tuple form for tooling; counts are stored rates (Hz for Period/Random in the simulator).

        For ``Pulse`` mode, ``resolution`` (seconds per tick) is **required** so ``pulse_sigma_s``
        can be converted to tick sigma for :meth:`DataBlock.generate` compatibility.
        """
        if not self.enabled or self.mode is None:
            return None
        m = self.mode
        if m in ('Pulse', 'RandomPulse'):
            m = 'Pulse'
        if m == 'Period':
            return ('Period', self.period_count)
        if m == 'Random':
            return ('Random', self.random_count)
        if m == 'Pulse':
            if resolution is None or resolution <= 0 or not math.isfinite(resolution):
                raise ValueError('to_generate_tuple: Pulse mode requires a finite resolution > 0')
            sigma_ticks = float(self.pulse_sigma_s) / resolution
            return ('Pulse', self.pulse_count, self.pulse_events, sigma_ticks)
        raise ValueError('Unknown mode: {!r}'.format(self.mode))

    def detection_keep_probability(self) -> float:
        """Hard threshold: 100% detection if reference amplitude exceeds threshold, else 0%."""
        return 1.0 if self.reference_pulse_v > self.threshold_voltage else 0.0


class TimeTagSimulator(TimeTagDevice):
    """
    Virtual TimeTag source: periodically calls ``dataUpdate`` with a 1-D ``uint64`` stream.

    Each word is :func:`pack_timetag` (time tick in upper bits, channel in low 4 bits).
    Stream is sorted by time. Maximum **16** channels (hardware-style 4-bit channel field).

    **Units:** constructor and :class:`ChannelSettings` expose **seconds** where a duration applies
    (``update_interval_range_s``, ``dead_time_s``, ``pulse_sigma_s``, ``initial_sim_time_s``);
    :attr:`resolution` is **seconds per tick**. All synthesis and packed times use integer **ticks**
    inside the simulator.

    ``period_count`` and ``random_count`` are **event rates in Hz** (lab time). Each batch uses
    ``round(rate * Δt_lab)`` random draws or, for Period, samples of a **global** grid so phases stay
    aligned across batches. ``Pulse`` mode uses a global pulse grid (rate = ``pulse_count``) and
    draws ``round(pulse_events * Δt_lab)`` events around that grid.

    **Update rate (single knob):** ``update_interval_range_s`` draws a lab window width Δt (seconds)
    each tick; that becomes ``span_ticks = max(1, round(Δt / resolution))`` simulated ticks per push.

    **Wall-clock sync:** with ``realtime_pacing=True`` (default), after each chunk is synthesized
    and delivered the simulator sleeps if needed so **wall time for that step** is at least
    ``span_ticks * resolution`` seconds—i.e. program time tracks simulated lab time for the window.
    Set ``realtime_pacing=False`` for maximum throughput (e.g. benchmarks). The background thread
    uses an interruptible wait so :meth:`stop` can exit promptly during the pacing sleep.

    So lab-time advances in lockstep with wall-clock pacing (1 s of lab window per iteration ⇒
    ~1 s of wall time per iteration when work is faster than that window).
    """

    def __init__(
        self,
        dataUpdate: Callable[[np.ndarray], None],
        channel_count: int = DEFAULT_CHANNEL_COUNT,
        resolution: float = 1e-12,
        seed: Optional[int] = None,
        update_interval_range_s: Union[Tuple[float, float], float] = (0.010, 0.020),
        initial_sim_time_s: float = 0.0,
        realtime_pacing: bool = True,
    ):
        super().__init__(
            dataUpdate=dataUpdate,
            channel_count=channel_count,
            resolution=resolution,
            serial_number="SIMULATOR",
        )
        if not callable(dataUpdate):
            raise TypeError('dataUpdate must be callable')
        if channel_count < 1:
            raise ValueError('channel_count must be >= 1, got {!r}'.format(channel_count))
        if channel_count > MAX_PACKED_CHANNELS:
            raise ValueError(
                'Stream packing uses 4 channel bits; channel_count must be <= {}, got {}'.format(
                    MAX_PACKED_CHANNELS, channel_count
                )
            )
        self._dataUpdate = dataUpdate
        self._channel_count = int(channel_count)
        if resolution <= 0 or not math.isfinite(resolution):
            raise ValueError('resolution must be finite and > 0, got {!r}'.format(resolution))
        self.resolution = resolution
        self._rng = np.random.default_rng(seed)
        self._channels: List[ChannelSettings] = [ChannelSettings() for _ in range(self._channel_count)]
        if isinstance(update_interval_range_s, (int, float)):
            x = float(update_interval_range_s)
            self._interval_lo = self._interval_hi = x
        else:
            lo, hi = update_interval_range_s
            self._interval_lo = float(lo)
            self._interval_hi = float(hi)
            if self._interval_lo <= 0 or self._interval_hi < self._interval_lo:
                raise ValueError('Invalid update_interval_range_s: {!r}'.format(update_interval_range_s))
        self._cursor = int(round(initial_sim_time_s / resolution))
        self._realtime_pacing = bool(realtime_pacing)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._channel_count_rates: List[float] = [0.0] * self._channel_count
        self._update_chunk_count_rates = True

    @property
    def channel_count(self) -> int:
        return self._channel_count

    def channel(self, index: int) -> ChannelSettings:
        if index < 0 or index >= self._channel_count:
            raise IndexError('Channel index must be in 0..{}'.format(self._channel_count - 1))
        return self._channels[index]

    def set_channel(self, index: int, **kwargs) -> None:
        ch = self.channel(index)
        for k, v in kwargs.items():
            if not hasattr(ch, k):
                raise TypeError('ChannelSettings has no field {!r}'.format(k))
            setattr(ch, k, v)

    def reset_channels(self) -> None:
        self._channels = [ChannelSettings() for _ in range(self._channel_count)]

    def set_deadtime(self, channel: int, dead_time_s: float) -> None:
        self.set_channel(channel, dead_time_s=dead_time_s)

    def set_trigger_level(self, channel: int, trigger_level_v: float) -> None:
        self.set_channel(channel, threshold_voltage=trigger_level_v)

    def is_running(self) -> bool:
        t = self._thread
        return bool(t is not None and t.is_alive())

    def get_channel_settings(self, channel: int) -> dict:
        ch = self.channel(channel)
        return {
            "dead_time_s": ch.dead_time_s,
            "threshold_voltage": ch.threshold_voltage,
            "enabled": ch.enabled,
            "mode": ch.mode,
            "period_count": ch.period_count,
            "random_count": ch.random_count,
            "pulse_count": ch.pulse_count,
            "pulse_events": ch.pulse_events,
            "pulse_sigma_s": ch.pulse_sigma_s,
            "reference_pulse_v": ch.reference_pulse_v,
        }

    def get_channel_count_rates(self) -> List[float]:
        if not self.is_running():
            return [0.0] * self._channel_count
        return list(self._channel_count_rates)

    def start(self) -> None:
        """Start background thread that invokes ``dataUpdate`` at configured intervals."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name='TimeTagSimulator', daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the background thread (waits briefly for clean exit)."""
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=5.0)
            self._thread = None

    def _draw_interval_seconds(self) -> float:
        lo, hi = self._interval_lo, self._interval_hi
        return float(self._rng.uniform(lo, hi)) if hi > lo else lo

    def _interval_seconds_to_span_ticks(self, dt_s: float) -> int:
        if dt_s <= 0:
            raise ValueError('interval seconds must be positive')
        return max(1, int(round(dt_s / self.resolution)))

    def step(self) -> None:
        """
        Emit one chunk using the same rule as the background thread: draw one ``dt`` from
        ``update_interval_range_s``, convert to span ticks ``round(dt / resolution)``, synthesize
        that window, then optionally sleep so wall time catches up to the simulated window width
        (see ``realtime_pacing``). Does not start the thread.
        """
        t0 = time.perf_counter()
        dt = self._draw_interval_seconds()
        span_ticks = self._interval_seconds_to_span_ticks(dt)
        self._emit_chunk_for_span(span_ticks)
        self._pace_wall_clock_after_emit(span_ticks, t0, interruptible=False)

    def _lab_seconds_for_span(self, span_ticks: int) -> float:
        return float(span_ticks) * float(self.resolution)

    def _pace_wall_clock_after_emit(self, span_ticks: int, t_start: float, interruptible: bool) -> bool:
        """
        If realtime pacing is on, wait until wall time since ``t_start`` reaches the lab duration
        ``span_ticks * resolution``. Returns True if ``interruptible`` and stop was requested during
        wait; otherwise False.
        """
        if not self._realtime_pacing:
            return False
        dt_lab = self._lab_seconds_for_span(span_ticks)
        if not math.isfinite(dt_lab) or dt_lab <= 0:
            return self._stop.is_set() if interruptible else False
        delay = dt_lab - (time.perf_counter() - t_start)
        if delay <= 0:
            return self._stop.is_set() if interruptible else False
        if interruptible:
            return self._stop.wait(timeout=delay)
        time.sleep(delay)
        return False

    def _dead_ticks(self, dead_time_s: float) -> int:
        if dead_time_s <= 0:
            return 0
        return int(round(dead_time_s / self.resolution))

    @staticmethod
    def _apply_dead_time(sorted_ts: np.ndarray, dead_ticks: int) -> np.ndarray:
        if dead_ticks <= 0 or sorted_ts.size == 0:
            return sorted_ts
        ts = np.asarray(sorted_ts, dtype=np.int64, order='C')
        n = ts.size
        out = np.empty(n, dtype=np.int64)
        # Use Python int for last so (t - last) cannot int64-overflow (e.g. t=0, last=-2**63).
        last = -(2**63)
        k = 0
        dt = int(dead_ticks)
        for i in range(n):
            t = int(ts[i])
            if t - last >= dt:
                out[k] = t
                last = t
                k += 1
        return out[:k]

    def _apply_threshold(self, sorted_ts: np.ndarray, keep_prob: float) -> np.ndarray:
        if sorted_ts.size == 0 or keep_prob >= 1.0:
            return sorted_ts
        if keep_prob <= 0.0:
            return np.array([], dtype='<i8')
        mask = self._rng.random(sorted_ts.size) < keep_prob
        out = sorted_ts[mask]
        out.sort()
        return out.astype('<i8')

    @staticmethod
    def _ceil_div_nonneg(n: int, d: int) -> int:
        """``ceil(n / d)`` for ``n >= 0``, ``d > 0`` (integer math, no floats)."""
        if d <= 0:
            raise ValueError('divisor must be positive')
        if n <= 0:
            return 0
        return (n + d - 1) // d

    def _event_count_for_rate_hz(self, rate_hz: float, dt_s: float) -> int:
        if rate_hz <= 0.0 or dt_s <= 0.0:
            return 0
        return int(round(rate_hz * dt_s))

    def _synthesize_period_ticks(self, t0: int, t1: int, rate_hz: float) -> np.ndarray:
        """
        Equally spaced events on a global grid ``k * P`` (ticks), ``P = round(1/(rate_hz * resolution))``,
        intersected with ``[t0, t1)``.
        """
        if rate_hz <= 0.0 or t1 <= t0:
            return np.array([], dtype=np.int64)
        P = int(round(1.0 / (rate_hz * self.resolution)))
        if P < 1:
            P = 1
        k_lo = self._ceil_div_nonneg(t0, P)
        k_hi = (t1 - 1) // P
        if k_lo > k_hi:
            return np.array([], dtype=np.int64)
        k = np.arange(k_lo, k_hi + 1, dtype=np.int64)
        return k * np.int64(P)

    def _synthesize_random_ticks(self, t0: int, t1: int, rate_hz: float) -> np.ndarray:
        span_ticks = t1 - t0
        dt_s = span_ticks * self.resolution
        n = self._event_count_for_rate_hz(rate_hz, dt_s)
        if n <= 0 or span_ticks <= 0:
            return np.array([], dtype=np.int64)
        raw = self._rng.integers(t0, t1, size=n, dtype=np.int64, endpoint=False)
        raw.sort()
        return raw

    def _synthesize_pulse_ticks(self, t0: int, t1: int, ch: ChannelSettings) -> np.ndarray:
        """Pulse mode on a global phase-locked grid, with optional Gaussian timing jitter."""
        span_ticks = t1 - t0
        if span_ticks <= 0:
            return np.array([], dtype=np.int64)
        dt_s = span_ticks * self.resolution
        pulse_count = max(1, int(round(ch.pulse_count * dt_s)))
        event_count = max(1, int(round(ch.pulse_events * dt_s)))
        sigma_ticks = float(ch.pulse_sigma_s) / self.resolution
        if pulse_count < 1 or event_count < 1:
            return np.array([], dtype=np.int64)
        pulse_rate_hz = float(ch.pulse_count)
        centers = self._synthesize_period_ticks(t0, t1, pulse_rate_hz)
        if centers.size == 0:
            return np.array([], dtype=np.int64)
        pulse_indices = self._rng.integers(0, centers.size, size=event_count, endpoint=False)
        pulse_position = self._rng.normal(0.0, sigma_ticks, size=event_count)
        ts = (centers[pulse_indices].astype(np.float64) + pulse_position).astype(np.int64)
        ts.sort()
        return ts

    def _synthesize_content(self, data_time_begin: int, data_time_end: int) -> List[np.ndarray]:
        if data_time_end <= data_time_begin:
            raise ValueError('data_time_end must be greater than data_time_begin')
        t0 = int(data_time_begin)
        t1 = int(data_time_end)
        dead_ticks_list = [self._dead_ticks(ch.dead_time_s) for ch in self._channels]
        keep_probs = [ch.detection_keep_probability() for ch in self._channels]
        new_content: List[np.ndarray] = []
        for ch_idx, ch in enumerate(self._channels):
            if not ch.enabled or ch.mode is None:
                new_content.append(np.array([], dtype=np.int64))
                continue
            mode = ch.mode
            if mode in ('Pulse', 'RandomPulse'):
                mode = 'Pulse'
            if mode == 'Period':
                ts = self._synthesize_period_ticks(t0, t1, float(ch.period_count))
            elif mode == 'Random':
                ts = self._synthesize_random_ticks(t0, t1, float(ch.random_count))
            elif mode == 'Pulse':
                ts = self._synthesize_pulse_ticks(t0, t1, ch)
            else:
                raise ValueError('Unknown channel mode: {!r}'.format(ch.mode))
            if ts.size == 0:
                new_content.append(np.array([], dtype=np.int64))
                continue
            ts = np.asarray(ts, dtype=np.int64, order='C')
            ts = self._apply_dead_time(ts, dead_ticks_list[ch_idx])
            ts = self._apply_threshold(ts, keep_probs[ch_idx])
            new_content.append(ts.astype(np.int64))
        return new_content

    def _content_to_packed_stream(self, content: List[np.ndarray]) -> np.ndarray:
        """
        Merge per-channel (already time-sorted) tick arrays into one global time order.
        Uses a single NumPy sort instead of Python list/tuple materialization.
        """
        sizes = [int(ts.size) for ts in content]
        n = sum(sizes)
        if n == 0:
            return np.array([], dtype=np.uint64)
        times = np.empty(n, dtype=np.int64)
        chans = np.empty(n, dtype=np.int64)
        off = 0
        for ch_idx, ts in enumerate(content):
            m = sizes[ch_idx]
            if m:
                times[off : off + m] = np.asarray(ts, dtype=np.int64)
                chans[off : off + m] = ch_idx
            off += m
        order = np.argsort(times, kind='mergesort')
        return pack_timetag(times[order], chans[order])

    def _emit_chunk_for_span(self, span_ticks: int) -> None:
        if span_ticks < 1:
            span_ticks = 1
        t0 = self._cursor
        t1 = t0 + span_ticks
        content = self._synthesize_content(t0, t1)
        self._cursor = t1
        if self._update_chunk_count_rates:
            dt_s = span_ticks * self.resolution
            for ch_idx, ts in enumerate(content):
                self._channel_count_rates[ch_idx] = int(ts.size / dt_s) if dt_s > 0 else 0
        arr = self._content_to_packed_stream(content)
        self._dataUpdate(arr)

    def _loop(self) -> None:
        while not self._stop.is_set():
            t0 = time.perf_counter()
            dt = self._draw_interval_seconds()
            span_ticks = self._interval_seconds_to_span_ticks(dt)
            self._emit_chunk_for_span(span_ticks)
            if self._pace_wall_clock_after_emit(span_ticks, t0, interruptible=True):
                break


if __name__ == '__main__':
    # From repo root: python -m pytimetag.device.Simulator

    def _demo():
        print('TimeTagSimulator demo (1 tick = 1 ps at default resolution 1e-12 s)\n')
        w = pack_timetag(np.array([12345], dtype=np.int64), np.array([7], dtype=np.int64))
        t, ch = unpack_timetag(w)
        print('pack_timetag([12345], [7]) -> {}  |  unpack -> t={}, ch={}\n'.format(w, int(t[0]), int(ch[0])))

        batch_no = [0]

        def on_data(events: np.ndarray):
            batch_no[0] += 1
            print('  batch {:2d}: {:4d} uint64 events'.format(batch_no[0], events.size))
            if events.size:
                tt, cc = unpack_timetag(events[:2])
                for i in range(tt.size):
                    print('      decode: channel={}  time_tick={}'.format(int(cc[i]), int(tt[i])))
            if events.size > 2:
                print('      ...')

        sim = TimeTagSimulator(
            on_data,
            channel_count=4,
            resolution=1e-12,
            seed=1,
            update_interval_range_s=(0.05, 0.08),
        )
        sim.set_channel(0, mode='Period', period_count=200, threshold_voltage=-0.5, reference_pulse_v=1.0)
        sim.set_channel(1, mode='Random', random_count=80, threshold_voltage=0.0, reference_pulse_v=1.0)

        print('Single step() (no background thread):')
        sim.step()
        print('')
        print('start() ~0.25 s then stop():')
        sim.start()
        time.sleep(0.25)
        sim.stop()
        print('\nDone.')

    _demo()
