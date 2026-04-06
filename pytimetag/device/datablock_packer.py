__license__ = "GNU General Public License v3"

"""
Pack sorted (time, channel) streams into :class:`~pytimetag.datablock.DataBlock`
instances, with multiple independent paths (split rules + optional channel filters).

Intended use: pass :meth:`DataBlockStreamPacker.feed_from_packed` or the result of
:func:`feed_callback_for_simulator` as ``dataUpdate`` to :class:`TimeTagSimulator`.
Input events must be **sorted by timestamp** (as produced by the simulator).
"""

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

import numba
import numpy as np
from numba.typed import List as NumbaList

from pytimetag.datablock import DataBlock

from pytimetag.device.Simulator import MAX_PACKED_CHANNELS


def _filter_by_channel_mask(
    timestamps: np.ndarray, channels: np.ndarray, mask: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Vectorized channel whitelist (``mask`` length 16, uint8 0/1)."""
    good = mask[channels] != 0
    return timestamps[good], channels[good]


@numba.njit(cache=True)
def _first_index_channel(channels: np.ndarray, target: int) -> int:
    for i in range(channels.shape[0]):
        if channels[i] == target:
            return i
    return -1


@numba.njit(cache=True)
def _pack_flat_to_content_jit(timestamps, channels):
    """Pack contiguous int64 (ts, ch) into 16 per-channel arrays (two passes, one kernel)."""
    n = timestamps.shape[0]
    sizes = np.zeros(MAX_PACKED_CHANNELS, dtype=np.int64)
    for i in range(n):
        c = channels[i]
        if 0 <= c < MAX_PACKED_CHANNELS:
            sizes[c] += 1
    contents = [np.empty(sizes[c], dtype=np.int64) for c in range(MAX_PACKED_CHANNELS)]
    ps = np.zeros(MAX_PACKED_CHANNELS, dtype=np.int64)
    for i in range(n):
        c = channels[i]
        if 0 <= c < MAX_PACKED_CHANNELS:
            j = ps[c]
            contents[c][j] = timestamps[i]
            ps[c] = j + 1
    return contents


def _pack_flat_to_content(timestamps: np.ndarray, channels: np.ndarray):
    ts = timestamps
    if ts.dtype != np.int64 or not ts.flags.c_contiguous:
        ts = np.ascontiguousarray(ts, dtype=np.int64)
    ch = channels
    if ch.dtype != np.int64 or not ch.flags.c_contiguous:
        ch = np.ascontiguousarray(ch, dtype=np.int64)
    return _pack_flat_to_content_jit(ts, ch)


@numba.njit(cache=True)
def _unpack_words_to_ts_ch(words_u64, out_ts, out_ch):
    """Unpack packed uint64 timetag stream (same layout as :func:`~pytimetag.device.Simulator.unpack_timetag`)."""
    n = words_u64.shape[0]
    for i in range(n):
        wi = np.uint64(words_u64[i])
        out_ch[i] = np.int64(wi & np.uint64(15))
        tu = wi >> np.uint64(4)
        out_ts[i] = np.int64(tu)


@numba.njit(cache=True)
def _generate_data_block_content(timestamps_buffer, channels_buffer):
    sizes = np.zeros(MAX_PACKED_CHANNELS, dtype=np.int64)
    nsec = len(timestamps_buffer)
    for section in range(nsec):
        channels = channels_buffer[section]
        for i in range(len(channels)):
            c = channels[i]
            if 0 <= c < MAX_PACKED_CHANNELS:
                sizes[c] += 1
    contents = [np.zeros(sizes[c], dtype=np.int64) for c in range(MAX_PACKED_CHANNELS)]
    ps = np.zeros(MAX_PACKED_CHANNELS, dtype=np.int64)
    for section in range(nsec):
        timestamps = timestamps_buffer[section]
        channels = channels_buffer[section]
        for i in range(len(channels)):
            c = channels[i]
            if 0 <= c < MAX_PACKED_CHANNELS:
                contents[c][ps[c]] = timestamps[i]
                ps[c] += 1
    return contents


def _to_numba_section_list(arrays: Sequence[np.ndarray]) -> NumbaList:
    out = NumbaList()
    for a in arrays:
        out.append(np.ascontiguousarray(a, dtype=np.int64))
    return out


def _make_channel_mask(allow: Optional[Sequence[int]]) -> np.ndarray:
    m = np.zeros(MAX_PACKED_CHANNELS, dtype=np.uint8)
    if allow is None:
        m[:] = 1
    else:
        for c in allow:
            ci = int(c)
            if 0 <= ci < MAX_PACKED_CHANNELS:
                m[ci] = 1
    return m


@dataclass
class SplitByTimeWindow:
    """Close a block when an event would reach or pass ``window_ticks`` after the block's first timestamp."""

    window_ticks: int


@dataclass
class SplitByChannelEvent:
    """
    Close a block before the first event on ``channel`` (0..15).
    That event becomes the first event of the next block.
    """

    channel: int


@dataclass
class DataBlockPackerPath:
    """One independent packing lane."""

    name: str
    split: Union[SplitByTimeWindow, SplitByChannelEvent]
    channels: Optional[Tuple[int, ...]] = None
    """If set, only these channel indices are kept (0..15)."""

    channel_count: int = MAX_PACKED_CHANNELS
    resolution: float = 1e-12


class _LaneState:
    __slots__ = ('cfg', 'mask', 'skip_channel_filter', 'buf_ts_parts', 'buf_ch_parts', 'buf_size')

    def __init__(self, cfg: DataBlockPackerPath):
        if cfg.channel_count != MAX_PACKED_CHANNELS:
            raise ValueError(
                'channel_count must be {}, got {}'.format(MAX_PACKED_CHANNELS, cfg.channel_count)
            )
        self.cfg = cfg
        self.mask = _make_channel_mask(cfg.channels)
        self.skip_channel_filter = cfg.channels is None
        self.buf_ts_parts: List[np.ndarray] = []
        self.buf_ch_parts: List[np.ndarray] = []
        self.buf_size = 0


class DataBlockStreamPacker:
    """
    Synchronously pack one stream into several :class:`~pytimetag.datablock.DataBlock` lanes.

    Each lane has its own split policy and optional channel whitelist. Call :meth:`feed`
    (or :meth:`feed_from_packed`) whenever a new sorted chunk arrives; completed blocks are
    returned per lane name. Call :meth:`flush` when the stream ends to emit tail buffers.
    """

    def __init__(self, paths: Sequence[DataBlockPackerPath]):
        if not paths:
            raise ValueError('paths must be non-empty')
        names = [p.name for p in paths]
        if len(set(names)) != len(names):
            raise ValueError('path names must be unique')
        self._lanes = [_LaneState(p) for p in paths]

    def reset(self) -> None:
        for ln in self._lanes:
            ln.buf_ts_parts = []
            ln.buf_ch_parts = []
            ln.buf_size = 0

    def _append(self, ln: _LaneState, ts: np.ndarray, ch: np.ndarray) -> None:
        if ts.size == 0:
            return
        ln.buf_ts_parts.append(ts)
        ln.buf_ch_parts.append(ch)
        ln.buf_size += int(ts.size)

    def _emit_block_sections(
        self,
        ln: _LaneState,
        ts_sections: Sequence[np.ndarray],
        ch_sections: Sequence[np.ndarray],
        creation_ms: float,
    ) -> DataBlock:
        if not ts_sections:
            raise ValueError('internal: empty emit')
        if len(ts_sections) == 1:
            content = _pack_flat_to_content(ts_sections[0], ch_sections[0])
        else:
            ts_nb = _to_numba_section_list(ts_sections)
            ch_nb = _to_numba_section_list(ch_sections)
            content = _generate_data_block_content(ts_nb, ch_nb)
            time2 = time.perf_counter()
        t0 = int(np.int64(ts_sections[0][0]))
        t1 = int(np.int64(ts_sections[-1][-1]))
        db = DataBlock.create(content, creation_ms, t0, t1, resolution=ln.cfg.resolution)
        return db

    def _split_prefix_sections(
        self, ln: _LaneState, take: int
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        if take <= 0 or take > ln.buf_size:
            raise ValueError('internal: bad take size')
        emit_ts_parts: List[np.ndarray] = []
        emit_ch_parts: List[np.ndarray] = []
        rem_ts_parts: List[np.ndarray] = []
        rem_ch_parts: List[np.ndarray] = []
        left = int(take)
        for ts, ch in zip(ln.buf_ts_parts, ln.buf_ch_parts):
            n = int(ts.size)
            if n == 0:
                continue
            if left <= 0:
                rem_ts_parts.append(ts)
                rem_ch_parts.append(ch)
                continue
            if left >= n:
                emit_ts_parts.append(ts)
                emit_ch_parts.append(ch)
                left -= n
                continue
            # Split inside current chunk.
            emit_ts = ts[:left]
            emit_ch = ch[:left]
            if emit_ts.size > 0:
                emit_ts_parts.append(emit_ts)
                emit_ch_parts.append(emit_ch)
            rem_ts = ts[left:]
            rem_ch = ch[left:]
            if rem_ts.size > 0:
                rem_ts_parts.append(rem_ts)
                rem_ch_parts.append(rem_ch)
            left = 0
        if left != 0:
            raise ValueError('internal: prefix split mismatch')
        ln.buf_ts_parts = rem_ts_parts
        ln.buf_ch_parts = rem_ch_parts
        ln.buf_size -= int(take)
        return emit_ts_parts, emit_ch_parts

    def _process_lane(
        self,
        ln: _LaneState,
        ts: np.ndarray,
        ch: np.ndarray,
        creation_ms: float,
    ) -> List[DataBlock]:
        out: List[DataBlock] = []
        self._append(ln, ts, ch)
        split_cfg = ln.cfg.split

        while ln.buf_size > 0:
            if isinstance(split_cfg, SplitByTimeWindow):
                w = split_cfg.window_ticks
                if w <= 0:
                    raise ValueError('window_ticks must be positive')
                start = int(np.int64(ln.buf_ts_parts[0][0]))
                end_excl = start + w
                split = 0
                consumed = 0
                for part_ts in ln.buf_ts_parts:
                    p = int(np.searchsorted(part_ts, end_excl, side='left'))
                    if p < part_ts.size:
                        split = consumed + p
                        break
                    consumed += int(part_ts.size)
                if split <= 0:
                    break
                if split == ln.buf_size:
                    break
                emit_ts_parts, emit_ch_parts = self._split_prefix_sections(ln, split)
            elif isinstance(split_cfg, SplitByChannelEvent):
                trig = split_cfg.channel
                if trig < 0 or trig >= MAX_PACKED_CHANNELS:
                    raise ValueError('split channel must be in 0..{}'.format(MAX_PACKED_CHANNELS - 1))
                # Find the first trigger globally in segmented buffer.
                first = -1
                consumed = 0
                for part_ch in ln.buf_ch_parts:
                    k = int(_first_index_channel(part_ch, trig))
                    if k >= 0:
                        first = consumed + k
                        break
                    consumed += int(part_ch.size)
                if first < 0:
                    break
                if first == 0:
                    # Keep old behavior: if trigger is first event, wait for next trigger.
                    second = -1
                    skip = 1
                    consumed = 0
                    for part_ch in ln.buf_ch_parts:
                        n = int(part_ch.size)
                        if skip >= n:
                            skip -= n
                            consumed += n
                            continue
                        part_view = part_ch[skip:]
                        k2 = int(_first_index_channel(part_view, trig))
                        if k2 >= 0:
                            second = consumed + skip + k2
                            break
                        consumed += n
                        skip = 0
                    if second < 0:
                        break
                    # Keep trigger-at-head semantics from previous implementation:
                    # emit up to (but not including) the next trigger event.
                    take = second
                else:
                    take = first
                emit_ts_parts, emit_ch_parts = self._split_prefix_sections(ln, take)
            else:
                raise TypeError(type(split_cfg))

            if not emit_ts_parts:
                continue
            out.append(self._emit_block_sections(ln, emit_ts_parts, emit_ch_parts, creation_ms))
        return out

    def feed(self, timestamps: np.ndarray, channels: np.ndarray) -> Dict[str, List[DataBlock]]:
        """
        Feed one sorted chunk. ``timestamps`` and ``channels`` are int64, same length,
        channels in ``0..15``.

        All :class:`~pytimetag.datablock.DataBlock` instances produced by this single
        ``feed`` call share the same ``creationTime`` (milliseconds, captured once at call start).
        """
        ts = np.ascontiguousarray(timestamps, dtype=np.int64)
        ch = np.ascontiguousarray(channels, dtype=np.int64)
        if ts.shape != ch.shape:
            raise ValueError('timestamps and channels must have the same shape')
        creation_ms = time.time_ns() / 1e6
        result: Dict[str, List[DataBlock]] = {}
        for ln in self._lanes:
            if ln.skip_channel_filter:
                ft, fc = ts, ch
            else:
                ft, fc = _filter_by_channel_mask(ts, ch, ln.mask)
            blocks = self._process_lane(ln, ft, fc, creation_ms)
            if blocks:
                result[ln.cfg.name] = blocks
        return result

    def feed_from_packed(self, words: np.ndarray) -> Dict[str, List[DataBlock]]:
        """Unpack packed ``uint64`` words (simulator layout) then :meth:`feed`."""
        w = np.asarray(words, dtype=np.uint64, order='C')
        if not w.flags.c_contiguous:
            w = np.ascontiguousarray(w, dtype=np.uint64)
        n = int(w.shape[0])
        out_ts = np.empty(n, dtype=np.int64)
        out_ch = np.empty(n, dtype=np.int64)
        if n:
            _unpack_words_to_ts_ch(w, out_ts, out_ch)
        return self.feed(out_ts, out_ch)

    def flush(self) -> Dict[str, List[DataBlock]]:
        """Emit remaining buffered data for every lane (one block per non-empty buffer)."""
        creation_ms = time.time_ns() / 1e6
        result: Dict[str, List[DataBlock]] = {}
        for ln in self._lanes:
            if ln.buf_size == 0:
                continue
            ts = ln.buf_ts_parts
            ch = ln.buf_ch_parts
            ln.buf_ts_parts = []
            ln.buf_ch_parts = []
            ln.buf_size = 0
            db = self._emit_block_sections(ln, ts, ch, creation_ms)
            result[ln.cfg.name] = [db]
        return result


def feed_callback_for_simulator(
    packer: DataBlockStreamPacker,
    on_blocks: Optional[Callable[[str, DataBlock], None]] = None,
) -> Callable[[np.ndarray], None]:
    """
    Build a ``dataUpdate`` callable for :class:`TimeTagSimulator`.

    If ``on_blocks`` is given, it is invoked as ``on_blocks(name, block)`` for each completed
    block from :meth:`DataBlockStreamPacker.feed_from_packed`. Otherwise, blocks are discarded
    (still advances packer state).
    """

    def _cb(words: np.ndarray) -> None:
        d = packer.feed_from_packed(words)
        if on_blocks is None:
            return
        for name, lst in d.items():
            for b in lst:
                on_blocks(name, b)

    return _cb


def pack_timestamps_channels_to_content(
    timestamps_sections: Sequence[np.ndarray],
    channels_sections: Sequence[np.ndarray],
) -> List[np.ndarray]:
    """
    Merge multiple (ts, ch) sections into the 16-channel list layout used by :meth:`DataBlock.create`.

    Uses the same numba kernel as the stream packer (handy for tests or offline batching).
    """
    if len(timestamps_sections) != len(channels_sections):
        raise ValueError('section count mismatch')
    if len(timestamps_sections) == 1:
        ts0 = np.ascontiguousarray(timestamps_sections[0], dtype=np.int64)
        ch0 = np.ascontiguousarray(channels_sections[0], dtype=np.int64)
        return _pack_flat_to_content(ts0, ch0)
    ts_l = _to_numba_section_list(timestamps_sections)
    ch_l = _to_numba_section_list(channels_sections)
    return _generate_data_block_content(ts_l, ch_l)
