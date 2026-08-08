"""SeruTek HSPCL6 hardware backend.

The vendor DLL, raw timestamp decoder, :class:`TimeTagDevice` implementation,
factory, and CLI plugin live together here so SeruTek support remains a single
lazy-loaded Windows-specific module.
"""

from __future__ import annotations

import ctypes
import math
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple, Union

import numpy as np

from pytimetag.device.Simulator import MAX_PACKED_CHANNELS, pack_timetag
from pytimetag.device.base import DeviceInfo, TimeTagDevice, TimeTagDeviceFactory
from pytimetag.device.manager import device_type_manager


SERUTEK_CHANNEL_COUNT = 6
SERUTEK_PHYSICAL_RESOLUTION = 1e-12
SERUTEK_TIMESTAMP_BITS = 57
SERUTEK_TIMESTAMP_MASK = (1 << SERUTEK_TIMESTAMP_BITS) - 1
SERUTEK_TIMESTAMP_SIGN = 1 << (SERUTEK_TIMESTAMP_BITS - 1)
SERUTEK_TIMESTAMP_PERIOD = 1 << SERUTEK_TIMESTAMP_BITS
PYTIMETAG_MAX_TICK = (1 << 59) - 1

DEFAULT_SERUTEK_DLL = Path(
    r"C:\Program Files\Serutek\SeruTek-HSPC6\Tdc_Libusb_Dll.dll"
)
SERUTEK_DLL_ENV = "SERUTEK_TDC_DLL"
DEFAULT_SERUTEK_SERIAL = "USB0"


class SerutekError(RuntimeError):
    """Base error for SeruTek driver and acquisition failures."""


class SerutekDataError(SerutekError):
    """Raised when the DLL returns malformed or unrepresentable timestamp data."""


def resolve_serutek_dll_path(
    dll_path: Optional[Union[str, os.PathLike[str]]] = None,
) -> Path:
    """Resolve explicit path, ``SERUTEK_TDC_DLL``, then the vendor default."""
    if dll_path is not None:
        return Path(dll_path).expanduser()
    configured = os.environ.get(SERUTEK_DLL_ENV)
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_SERUTEK_DLL


class SerutekDLL:
    """Typed ctypes access to the HSPCL6 DLL subset used by PyTimeTag.

    ``library`` is only an injection point for tests. Production callers leave
    it as ``None`` and load the native DLL from ``dll_path``.
    """

    def __init__(
        self,
        dll_path: Optional[Union[str, os.PathLike[str]]] = None,
        *,
        library: Optional[Any] = None,
    ) -> None:
        self.path = resolve_serutek_dll_path(dll_path)
        self._dll_directory = None
        self._loader_closed = False

        if library is None:
            if os.name != "nt":
                raise SerutekError(
                    "SeruTek HSPCL6 support requires Windows and Tdc_Libusb_Dll.dll"
                )
            self.path = self.path.resolve()
            if not self.path.is_file():
                raise SerutekError(
                    f"SeruTek DLL not found: {self.path}. Set {SERUTEK_DLL_ENV} "
                    "or pass --driver-path."
                )
            try:
                self._dll_directory = os.add_dll_directory(str(self.path.parent))
                library = ctypes.CDLL(str(self.path))
            except OSError as exc:
                if self._dll_directory is not None:
                    self._dll_directory.close()
                    self._dll_directory = None
                raise SerutekError(
                    f"Could not load SeruTek DLL {self.path}: {exc}"
                ) from exc

        self.library = library
        self._bind_functions()

    def _bind(self, name: str, argtypes: list[Any], restype: Any) -> Any:
        try:
            function = getattr(self.library, name)
        except AttributeError as exc:
            raise SerutekError(
                f"SeruTek DLL does not export required function: {name}"
            ) from exc
        function.argtypes = argtypes
        function.restype = restype
        return function

    def _bind_functions(self) -> None:
        c_int = ctypes.c_int
        c_void_p = ctypes.c_void_p
        self._libusb_init = self._bind("LibUsb_Init", [], c_int)
        self._libusb_exit = self._bind("LibUsb_Exit", [], c_int)
        self._connection_test = self._bind("UsbConnTest", [], c_int)
        self._dacwrite = self._bind("dacwrite", [c_int, c_int], c_int)
        self._set_offset = self._bind("setuseroffset", [c_int, c_int], c_int)
        self._start_timestamps = self._bind("start_tstd_mmf_usb", [c_int], c_int)
        self._get_timestamp_data = self._bind(
            "get_tstd_mmf_usb_data", [c_int, c_void_p], c_int
        )
        self._stop_timestamps = self._bind("stop_tstd_mmf_usb", [], c_int)
        self._close_timestamp_mmf = self._bind("close_tstd_mmf", [], None)

    @staticmethod
    def _require_zero(operation: str, result: int) -> None:
        if int(result) != 0:
            raise SerutekError(
                f"SeruTek {operation} failed with return code {int(result)}"
            )

    def initialize(self) -> None:
        self._require_zero("LibUsb_Init", self._libusb_init())

    def exit(self) -> None:
        self._require_zero("LibUsb_Exit", self._libusb_exit())

    def connection_test(self) -> bool:
        return int(self._connection_test()) == 0

    def set_threshold_mv(self, channel_index: int, threshold_mv: int) -> None:
        if channel_index < 0 or channel_index >= SERUTEK_CHANNEL_COUNT:
            raise ValueError("SeruTek channel index must be in 0..5")
        if threshold_mv < 0 or threshold_mv > 4096:
            raise ValueError("SeruTek trigger threshold must be in 0..4096 mV")
        self._require_zero(
            f"dacwrite(channel={channel_index + 1})",
            self._dacwrite(int(channel_index), int(threshold_mv)),
        )

    def set_offset_ps(self, channel_index: int, offset_ps: int) -> None:
        if channel_index < 0 or channel_index >= SERUTEK_CHANNEL_COUNT:
            raise ValueError("SeruTek channel index must be in 0..5")
        if offset_ps < -(1 << 31) or offset_ps > (1 << 31) - 1:
            raise ValueError("SeruTek channel offset must fit a signed 32-bit integer")
        self._require_zero(
            f"setuseroffset(channel={channel_index + 1})",
            self._set_offset(int(channel_index + 1), int(offset_ps)),
        )

    def start_timestamps(self) -> None:
        self._require_zero("start_tstd_mmf_usb", self._start_timestamps(0))

    def read_timestamps(
        self,
        buffer: ctypes.Array[ctypes.c_char],
        max_bytes: int,
    ) -> bytes:
        received = int(
            self._get_timestamp_data(int(max_bytes), ctypes.byref(buffer))
        )
        if received < 0:
            raise SerutekError(
                "SeruTek get_tstd_mmf_usb_data failed with return code "
                f"{received}"
            )
        if received > max_bytes:
            raise SerutekError(
                f"SeruTek DLL returned {received} bytes for a {max_bytes}-byte buffer"
            )
        if not received:
            return b""
        return ctypes.string_at(ctypes.addressof(buffer), received)

    def stop_timestamps(self) -> None:
        self._require_zero("stop_tstd_mmf_usb", self._stop_timestamps())

    def close_timestamp_mmf(self) -> None:
        self._close_timestamp_mmf()

    def close_loader(self) -> None:
        if self._loader_closed:
            return
        self._loader_closed = True
        if self._dll_directory is not None:
            self._dll_directory.close()
            self._dll_directory = None


class SerutekTimestampDecoder:
    """Convert raw HSPCL6 records into PyTimeTag ticks and zero-based channels."""

    def __init__(self, resolution: float = SERUTEK_PHYSICAL_RESOLUTION) -> None:
        if resolution <= 0 or not math.isfinite(resolution):
            raise ValueError("resolution must be finite and positive")
        self.resolution = float(resolution)
        self.reset()

    def reset(self) -> None:
        self._carry = b""
        self._last_signed: Optional[int] = None
        self._wrap_offset = 0
        self._origin_ps: Optional[int] = None
        self.invalid_channel_records = 0

    def feed(self, data: bytes) -> Tuple[np.ndarray, np.ndarray]:
        payload = self._carry + bytes(data)
        complete_bytes = len(payload) - (len(payload) % 8)
        self._carry = payload[complete_bytes:]
        if complete_bytes == 0:
            empty = np.empty(0, dtype=np.int64)
            return empty, empty.copy()

        raw = np.frombuffer(payload[:complete_bytes], dtype="<u8")
        channels = (raw >> np.uint64(SERUTEK_TIMESTAMP_BITS)).astype(np.int64)
        signed = (raw & np.uint64(SERUTEK_TIMESTAMP_MASK)).astype(np.int64)
        negative = (signed & np.int64(SERUTEK_TIMESTAMP_SIGN)) != 0
        signed[negative] -= np.int64(SERUTEK_TIMESTAMP_PERIOD)

        previous = np.empty(signed.size, dtype=np.int64)
        previous[0] = signed[0] if self._last_signed is None else self._last_signed
        if signed.size > 1:
            previous[1:] = signed[:-1]
        delta = signed - previous
        wrap_steps = np.zeros(signed.size, dtype=np.int64)
        wrap_steps[delta < -SERUTEK_TIMESTAMP_SIGN] = 1
        wrap_steps[delta > SERUTEK_TIMESTAMP_SIGN] = -1
        epochs = self._wrap_offset + np.cumsum(wrap_steps, dtype=np.int64)
        unwrapped_ps = signed + epochs * np.int64(SERUTEK_TIMESTAMP_PERIOD)
        self._last_signed = int(signed[-1])
        self._wrap_offset = int(epochs[-1])

        valid = (channels >= 1) & (channels <= SERUTEK_CHANNEL_COUNT)
        invalid_count = int(valid.size - np.count_nonzero(valid))
        self.invalid_channel_records += invalid_count
        if invalid_count:
            unwrapped_ps = unwrapped_ps[valid]
            channels = channels[valid]
        if unwrapped_ps.size == 0:
            empty = np.empty(0, dtype=np.int64)
            return empty, empty.copy()

        # PyTimeTag's packed stream cannot preserve negative 60-bit ticks.
        # Anchor to the earliest valid event, never to vendor marker records.
        if self._origin_ps is None:
            self._origin_ps = int(unwrapped_ps.min())
        elapsed_ps = unwrapped_ps - np.int64(self._origin_ps)
        if self.resolution == SERUTEK_PHYSICAL_RESOLUTION:
            ticks = elapsed_ps
        else:
            ticks = np.rint(
                elapsed_ps.astype(np.float64)
                * (SERUTEK_PHYSICAL_RESOLUTION / self.resolution)
            ).astype(np.int64)
        channels = channels - 1

        if ticks.size and int(ticks.min()) < 0:
            raise SerutekDataError(
                "SeruTek timestamps moved before the acquisition origin; reduce "
                "channel offset skew or increase the polling interval"
            )
        if ticks.size and int(ticks.max()) > PYTIMETAG_MAX_TICK:
            raise SerutekDataError(
                "SeruTek acquisition exceeded the positive 60-bit PyTimeTag stream range"
            )
        if ticks.size > 1 and np.any(ticks[1:] < ticks[:-1]):
            order = np.argsort(ticks, kind="mergesort")
            ticks = ticks[order]
            channels = channels[order]
        return (
            np.ascontiguousarray(ticks, dtype=np.int64),
            np.ascontiguousarray(channels, dtype=np.int64),
        )

    def finish(self) -> None:
        if self._carry:
            trailing = len(self._carry)
            self._carry = b""
            raise SerutekDataError(
                f"SeruTek stream ended with {trailing} trailing byte(s)"
            )


@dataclass
class SerutekChannelSettings:
    threshold_voltage: float = 0.5
    offset_ps: int = 0
    enabled: bool = True


_SERUTEK_INSTANCE_GUARD = threading.Lock()


class SerutekTimeTag(TimeTagDevice):
    """SeruTek HSPCL6 T2 timestamp backend for PyTimeTag."""

    def __init__(
        self,
        serial_number: str,
        dataUpdate: Callable[[np.ndarray], None],
        channel_count: int = SERUTEK_CHANNEL_COUNT,
        resolution: float = SERUTEK_PHYSICAL_RESOLUTION,
        n_max_events: int = 4 * 1024 * 1024,
        poll_interval_s: float = 0.2,
        dll_path: Optional[Union[str, os.PathLike[str]]] = None,
        default_threshold_v: float = 0.5,
        *,
        driver: Optional[SerutekDLL] = None,
    ) -> None:
        super().__init__(
            dataUpdate=dataUpdate,
            channel_count=channel_count,
            resolution=resolution,
            serial_number=serial_number,
        )
        if self.channel_count != SERUTEK_CHANNEL_COUNT:
            raise ValueError("SeruTek HSPCL6 has exactly 6 channels")
        if self.channel_count > MAX_PACKED_CHANNELS:
            raise ValueError("SeruTek channel count exceeds PyTimeTag stream capacity")
        if serial_number not in (DEFAULT_SERUTEK_SERIAL, "default"):
            raise ValueError(
                f"SeruTek DLL exposes one addressable device; use {DEFAULT_SERUTEK_SERIAL!r}"
            )
        if n_max_events < 1:
            raise ValueError("n_max_events must be positive")
        if poll_interval_s <= 0 or not math.isfinite(poll_interval_s):
            raise ValueError("poll_interval_s must be finite and positive")
        max_bytes = int(n_max_events) * 8
        if max_bytes > (1 << 31) - 1:
            raise ValueError("SeruTek read buffer must be smaller than 2 GiB")

        if not _SERUTEK_INSTANCE_GUARD.acquire(blocking=False):
            raise SerutekError("Only one SeruTek DLL instance may be active per process")
        self._guard_held = True
        self._driver: Optional[SerutekDLL] = None
        self._initialized = False
        self._mmf_open = False
        self._closed = False
        self._max_bytes = max_bytes
        self._buffer = ctypes.create_string_buffer(max_bytes)
        self._poll_interval_s = float(poll_interval_s)
        self._decoder = SerutekTimestampDecoder(resolution)
        self._settings = [
            SerutekChannelSettings(threshold_voltage=float(default_threshold_v))
            for _ in range(SERUTEK_CHANNEL_COUNT)
        ]
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._thread_error: Optional[BaseException] = None
        self._state_lock = threading.Lock()

        try:
            self._driver = driver if driver is not None else SerutekDLL(dll_path)
            self._driver.initialize()
            self._initialized = True
            if not self._driver.connection_test():
                raise SerutekError("No connected SeruTek HSPCL6 was detected")
            for channel in range(SERUTEK_CHANNEL_COUNT):
                self.set_trigger_level(channel, default_threshold_v)
                self._driver.set_offset_ps(channel, 0)
        except BaseException:
            self._release_driver()
            raise

    def _ensure_channel(self, index: int) -> None:
        if index < 0 or index >= SERUTEK_CHANNEL_COUNT:
            raise IndexError("SeruTek channel index must be in 0..5")
        if self._closed:
            raise SerutekError("SeruTek device is closed")

    def set_channel(self, index: int, **kwargs: Any) -> None:
        self._ensure_channel(index)
        allowed = {"threshold_voltage", "offset_ps", "enabled"}
        unknown = set(kwargs) - allowed
        if unknown:
            raise ValueError(
                "Unsupported SeruTek channel setting(s): " + ", ".join(sorted(unknown))
            )
        if "threshold_voltage" in kwargs:
            self.set_trigger_level(index, float(kwargs["threshold_voltage"]))
        if "offset_ps" in kwargs:
            if self._mmf_open:
                raise SerutekError(
                    "Stop SeruTek acquisition before changing timestamp offsets"
                )
            offset_ps = int(kwargs["offset_ps"])
            self._driver.set_offset_ps(index, offset_ps)
            self._settings[index].offset_ps = offset_ps
        if "enabled" in kwargs:
            # The timestamp stream is filtered locally. The DLL's channel-enable
            # numbering is not documented well enough to call it safely here.
            self._settings[index].enabled = bool(kwargs["enabled"])

    def set_trigger_level(self, channel: int, trigger_level_v: float) -> None:
        self._ensure_channel(channel)
        voltage = float(trigger_level_v)
        if not math.isfinite(voltage) or voltage < 0 or voltage > 4.096:
            raise ValueError("SeruTek trigger level must be in 0..4.096 V")
        threshold_mv = int(round(voltage * 1000.0))
        self._driver.set_threshold_mv(channel, threshold_mv)
        self._settings[channel].threshold_voltage = threshold_mv / 1000.0

    def set_deadtime(self, channel: int, dead_time_s: float) -> None:
        self._ensure_channel(channel)
        raise NotImplementedError(
            "HSPCL6 has no general per-channel dead-time control; channel 1 "
            "sync holdoff is a separate vendor-specific feature"
        )

    def get_channel_settings(self, channel: int) -> dict[str, Any]:
        """Return GUI-safe settings and hardware capability flags."""
        self._ensure_channel(channel)
        settings = self._settings[channel]
        return {
            "threshold_voltage": settings.threshold_voltage,
            "offset_ps": settings.offset_ps,
            "enabled": settings.enabled,
            "dead_time_s": None,
            "supports_threshold_voltage": True,
            "supports_offset_ps": True,
            "supports_enabled": True,
            "supports_dead_time": False,
        }

    def get_channel_count_rates(self) -> List[float]:
        return list(getattr(self, "_channel_count_rates", [0.0] * self.channel_count))

    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive() and not self._stop_event.is_set())

    def start(self) -> None:
        with self._state_lock:
            if self._closed:
                raise SerutekError("SeruTek device is closed")
            if self._thread is not None and self._thread.is_alive():
                return
            self._decoder.reset()
            self._thread_error = None
            self._stop_event.clear()
            self._driver.start_timestamps()
            self._mmf_open = True
            self._thread = threading.Thread(
                target=self._loop,
                name="SerutekTimeTag",
                daemon=True,
            )
            try:
                self._thread.start()
            except BaseException:
                self._driver.stop_timestamps()
                self._driver.close_timestamp_mmf()
                self._mmf_open = False
                self._thread = None
                raise

    def _emit_bytes(self, data: bytes) -> None:
        ticks, channels = self._decoder.feed(data)
        if ticks.size == 0:
            return
        enabled = np.fromiter(
            (self._settings[int(ch)].enabled for ch in channels),
            dtype=np.bool_,
            count=channels.size,
        )
        if not np.all(enabled):
            ticks = ticks[enabled]
            channels = channels[enabled]
        if ticks.size:
            self._dataUpdate(pack_timetag(ticks, channels))

    def _loop(self) -> None:
        try:
            while not self._stop_event.wait(self._poll_interval_s):
                chunk = self._driver.read_timestamps(self._buffer, self._max_bytes)
                if chunk:
                    self._emit_bytes(chunk)
        except BaseException as exc:
            self._thread_error = exc
            self._stop_event.set()

    def raise_if_failed(self) -> None:
        if self._thread_error is not None:
            raise SerutekError("SeruTek acquisition thread failed") from self._thread_error

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(5.0, self._poll_interval_s * 3.0))
            if thread.is_alive() and self._thread_error is None:
                self._thread_error = SerutekError(
                    "SeruTek acquisition thread did not stop in time"
                )
        self._thread = None

        cleanup_error: Optional[BaseException] = None
        if self._mmf_open:
            try:
                self._driver.stop_timestamps()
                tail = self._driver.read_timestamps(self._buffer, self._max_bytes)
                if tail:
                    self._emit_bytes(tail)
                self._decoder.finish()
            except BaseException as exc:
                cleanup_error = exc
            finally:
                try:
                    self._driver.close_timestamp_mmf()
                except BaseException as exc:
                    if cleanup_error is None:
                        cleanup_error = exc
                self._mmf_open = False

        error = self._thread_error if self._thread_error is not None else cleanup_error
        self._thread_error = None
        if error is not None:
            raise SerutekError("SeruTek acquisition failed") from error

    def _release_driver(self) -> None:
        exit_error: Optional[BaseException] = None
        if self._initialized:
            try:
                self._driver.exit()
            except BaseException as exc:
                exit_error = exc
            self._initialized = False
        try:
            if self._driver is not None:
                self._driver.close_loader()
        finally:
            if self._guard_held:
                self._guard_held = False
                _SERUTEK_INSTANCE_GUARD.release()
        if exit_error is not None:
            raise SerutekError("SeruTek LibUsb_Exit failed") from exit_error

    def close(self) -> None:
        if self._closed:
            return
        stop_error: Optional[BaseException] = None
        try:
            self.stop()
        except BaseException as exc:
            stop_error = exc
        self._closed = True
        try:
            self._release_driver()
        except BaseException as exc:
            if stop_error is None:
                stop_error = exc
        if stop_error is not None:
            raise stop_error


class SerutekTimeTagFactory(TimeTagDeviceFactory):
    device_type = "serutek"

    @classmethod
    def discover_at(
        cls,
        dll_path: Optional[Union[str, os.PathLike[str]]] = None,
    ) -> List[DeviceInfo]:
        if os.name != "nt":
            return []
        driver = SerutekDLL(dll_path)
        initialized = False
        try:
            driver.initialize()
            initialized = True
            if not driver.connection_test():
                return []
            return [
                DeviceInfo(
                    device_type=cls.device_type,
                    serial_number=DEFAULT_SERUTEK_SERIAL,
                    model_name="HSPCL6",
                    metadata={
                        "channel_count": SERUTEK_CHANNEL_COUNT,
                        "resolution": SERUTEK_PHYSICAL_RESOLUTION,
                        "dll_path": str(driver.path),
                    },
                )
            ]
        finally:
            try:
                if initialized:
                    driver.exit()
            finally:
                driver.close_loader()

    @classmethod
    def discover(cls) -> List[DeviceInfo]:
        return cls.discover_at()

    @classmethod
    def connect(
        cls,
        serial_number: str,
        dataUpdate: Callable[[np.ndarray], None],
        **kwargs: Any,
    ) -> SerutekTimeTag:
        return SerutekTimeTag(
            serial_number=serial_number,
            dataUpdate=dataUpdate,
            **kwargs,
        )


def create_device(
    manager: Any,
    args: Any,
    console: Any,
    live: Any,
    on_words: Callable[[np.ndarray, Any], None],
) -> SerutekTimeTag:
    """CLI plugin entry point for ``--source serutek``."""
    dll_path = getattr(args, "driver_path", None)
    devices = SerutekTimeTagFactory.discover_at(dll_path)
    if not devices:
        raise RuntimeError(
            "No connected SeruTek HSPCL6 found. Check USB power/driver and the DLL path."
        )
    available = [device.serial_number for device in devices]
    serial = getattr(args, "serial", None) or available[0]
    if serial not in available:
        raise RuntimeError(
            f"Requested --serial {serial!r} not found. Available: {', '.join(available)}"
        )
    console.print(
        f"Device serial: [cyan]{serial}[/cyan] (SeruTek HSPCL6, DLL: "
        f"[dim]{resolve_serutek_dll_path(dll_path)}[/dim])"
    )
    return manager.connect(
        "serutek",
        serial_number=serial,
        dataUpdate=lambda words: on_words(words, live),
        channel_count=args.channel_count,
        resolution=args.resolution,
        n_max_events=args.hardware_buffer_size,
        poll_interval_s=args.hardware_poll_s,
        dll_path=dll_path,
    )


device_type_manager.register(SerutekTimeTagFactory)
