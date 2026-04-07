from __future__ import annotations

import re
import threading
import time
import warnings
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from pytimetag.device.Simulator import MAX_PACKED_CHANNELS, pack_timetag
from pytimetag.device.base import DeviceInfo, TimeTagDevice, TimeTagDeviceFactory
from pytimetag.device.manager import device_type_manager


class SwabianNumPyABIError(ImportError):
    """Raised when the Swabian ``_TimeTagger`` extension does not match the installed NumPy ABI."""


def _looks_like_numpy_abi_failure(msg: str) -> bool:
    """Detect NumPy C-API / ABI mismatch when loading Swabian's ``_TimeTagger``."""
    if not msg:
        return False
    needles = (
        "_ARRAY_API",
        "numpy.core.multiarray failed to import",
        "compiled using NumPy 1.x",
        "cannot be run in",
        "NumPy 2.2",
        "NumPy 2.",
        "must be compiled with NumPy 2.0",
    )
    if any(n in msg for n in needles):
        return True
    # Catch multi-line numpy warning text when coerced to str
    if re.search(r"NumPy\s+1\.x.*NumPy\s+2", msg, re.DOTALL):
        return True
    return False


def _load_timetagger():
    # Avoid flooding stderr with NumPy ABI RuntimeWarnings when the extension mismatches NumPy 2.x.
    warnings.filterwarnings(
        "ignore",
        message=r".*A module that was compiled using NumPy 1\.x cannot be run in.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=r".*Some module may need to rebuild instead.*",
    )
    try:
        import TimeTagger  # type: ignore
    except Exception as e:
        msg = str(e)
        if _looks_like_numpy_abi_failure(msg):
            raise SwabianNumPyABIError(
                "Swabian TimeTagger native module (_TimeTagger) does not match this environment's NumPy ABI."
            ) from None
        raise ImportError(
            "Swabian device support requires the optional Swabian Python driver. "
            "Install extras with: pip install \"pytimetag[swabian]\""
        ) from e
    return TimeTagger


@dataclass
class SwabianChannelSettings:
    dead_time_s: Optional[float] = None
    threshold_voltage: Optional[float] = None
    enabled: bool = True


class SwabianTimeTag(TimeTagDevice):
    """Swabian Time Tagger backend with the same dataUpdate stream contract as the simulator."""

    def __init__(
        self,
        serial_number: str,
        dataUpdate: Callable[[np.ndarray], None],
        channel_count: int = 8,
        resolution: float = 1e-12,
        n_max_events: int = int(1e6),
        poll_interval_s: float = 0.002,
    ):
        super().__init__(
            dataUpdate=dataUpdate,
            channel_count=channel_count,
            resolution=resolution,
            serial_number=serial_number,
        )
        if self.channel_count > MAX_PACKED_CHANNELS:
            raise ValueError(
                f"Stream packing uses 4 channel bits; channel_count must be <= {MAX_PACKED_CHANNELS}"
            )
        if poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be positive")
        self._n_max_events = int(n_max_events)
        self._poll_interval_s = float(poll_interval_s)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._settings: List[SwabianChannelSettings] = [SwabianChannelSettings() for _ in range(self.channel_count)]

        tt = _load_timetagger()
        self._tt = tt
        self._tagger = tt.createTimeTagger(serial_number)
        self._stream = None

    def _channel_to_hw(self, channel: int) -> int:
        if channel < 0 or channel >= self.channel_count:
            raise IndexError(f"channel index must be in 0..{self.channel_count - 1}")
        return int(channel + 1)

    def _seconds_to_ps(self, seconds: float) -> int:
        if seconds < 0:
            raise ValueError("dead_time_s must be >= 0")
        return int(round(float(seconds) * 1e12))

    def set_channel(self, index: int, **kwargs) -> None:
        hw = self._channel_to_hw(index)
        st = self._settings[index]
        if "dead_time_s" in kwargs:
            st.dead_time_s = float(kwargs["dead_time_s"])
            self._tagger.setDeadtime(hw, self._seconds_to_ps(st.dead_time_s))
        if "deadtime_ps" in kwargs:
            deadtime_ps = int(kwargs["deadtime_ps"])
            st.dead_time_s = deadtime_ps / 1e12
            self._tagger.setDeadtime(hw, deadtime_ps)
        if "threshold_voltage" in kwargs:
            st.threshold_voltage = float(kwargs["threshold_voltage"])
            self._tagger.setTriggerLevel(hw, st.threshold_voltage)
        if "enabled" in kwargs:
            st.enabled = bool(kwargs["enabled"])
            # Swabian API has no generic channel disable here; we keep local filter behavior only.

    def set_deadtime(self, channel: int, dead_time_s: float) -> None:
        self.set_channel(channel, dead_time_s=dead_time_s)

    def set_trigger_level(self, channel: int, trigger_level_v: float) -> None:
        self.set_channel(channel, threshold_voltage=trigger_level_v)

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._stream = self._tt.TimeTagStream(
                tagger=self._tagger,
                n_max_events=self._n_max_events,
                channels=[i for i in range(1, self.channel_count + 1)],
            )
            self._stream.start()
            self._thread = threading.Thread(target=self._loop, name="SwabianTimeTag", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=5.0)
            self._thread = None
        if self._stream is not None:
            try:
                self._stream.stop()
            except BaseException:
                pass
            self._stream = None

    def close(self) -> None:
        self.stop()
        if self._tagger is not None:
            try:
                self._tt.freeTimeTagger(self._tagger)
            finally:
                self._tagger = None

    def _extract_size(self, data: Any) -> int:
        size_attr = getattr(data, "size", None)
        if callable(size_attr):
            return int(size_attr())
        if size_attr is not None:
            return int(size_attr)
        timestamps = data.getTimestamps()
        return int(np.asarray(timestamps).size)

    def _loop(self) -> None:
        while not self._stop.is_set():
            stream = self._stream
            if stream is None:
                break
            try:
                data = stream.getData()
                if self._extract_size(data) <= 0:
                    time.sleep(self._poll_interval_s)
                    continue
                ts_raw = np.asarray(data.getTimestamps(), dtype=np.int64)
                ch_raw = np.asarray(data.getChannels(), dtype=np.int64) - 1
                if ts_raw.size == 0:
                    time.sleep(self._poll_interval_s)
                    continue
                valid = (ch_raw >= 0) & (ch_raw < self.channel_count)
                if not np.all(valid):
                    ts_raw = ts_raw[valid]
                    ch_raw = ch_raw[valid]
                if ts_raw.size == 0:
                    time.sleep(self._poll_interval_s)
                    continue
                enabled_mask = np.array([self._settings[int(ch)].enabled for ch in ch_raw], dtype=bool)
                if not np.all(enabled_mask):
                    ts_raw = ts_raw[enabled_mask]
                    ch_raw = ch_raw[enabled_mask]
                if ts_raw.size == 0:
                    time.sleep(self._poll_interval_s)
                    continue
                if self.resolution != 1e-12:
                    ts = np.rint(ts_raw * (1e-12 / self.resolution)).astype(np.int64)
                else:
                    ts = ts_raw.astype(np.int64, copy=False)
                order = np.argsort(ts, kind="mergesort")
                words = pack_timetag(ts[order], ch_raw[order])
                self._dataUpdate(words)
            except BaseException:
                # Keep acquisition loop alive for transient transport/stream errors.
                time.sleep(self._poll_interval_s)


class SwabianTimeTagFactory(TimeTagDeviceFactory):
    device_type = "swabian"

    @classmethod
    def discover(cls) -> List[DeviceInfo]:
        tt = _load_timetagger()
        # Newer versions support include_model_name; older ones only accept no args.
        try:
            entries = tt.scanTimeTagger(include_model_name=True)
        except TypeError:
            entries = tt.scanTimeTagger()
        out: List[DeviceInfo] = []
        for ent in entries:
            text = str(ent)
            if "," in text:
                serial, model = text.split(",", 1)
                out.append(
                    DeviceInfo(
                        device_type=cls.device_type,
                        serial_number=serial.strip(),
                        model_name=model.strip() or None,
                    )
                )
            else:
                out.append(DeviceInfo(device_type=cls.device_type, serial_number=text.strip()))
        return out

    @classmethod
    def connect(
        cls,
        serial_number: str,
        dataUpdate: Callable[[np.ndarray], None],
        **kwargs,
    ) -> SwabianTimeTag:
        dev = SwabianTimeTag(serial_number=serial_number, dataUpdate=dataUpdate, **kwargs)
        return dev


device_type_manager.register(SwabianTimeTagFactory)
