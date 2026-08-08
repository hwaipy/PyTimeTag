import ctypes
import threading
import unittest
from collections import deque

import numpy as np

from pytimetag.device.SerutekTimeTag import (
    SERUTEK_TIMESTAMP_MASK,
    SERUTEK_TIMESTAMP_SIGN,
    SerutekDLL,
    SerutekDataError,
    SerutekError,
    SerutekTimeTag,
    SerutekTimestampDecoder,
)
from pytimetag.device.Simulator import unpack_timetag
from pytimetag.device.source_registry import (
    CLI_SOURCE_PLUGINS,
    get_cli_source_defaults,
)


def _raw_record(channel, timestamp_ps):
    return np.uint64(
        (int(channel) << 57) | (int(timestamp_ps) & SERUTEK_TIMESTAMP_MASK)
    )


def _raw_bytes(*records):
    return np.asarray(records, dtype="<u8").tobytes()


class _FakeFunction:
    def __init__(self, owner, name, implementation=None):
        self.owner = owner
        self.name = name
        self.implementation = implementation
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        self.owner.calls.append((self.name, args))
        if self.implementation is None:
            return 0
        return self.implementation(*args)


class _FakeLibrary:
    def __init__(self, chunks=()):
        self.calls = []
        self.chunks = deque(chunks)
        self.LibUsb_Init = _FakeFunction(self, "LibUsb_Init")
        self.LibUsb_Exit = _FakeFunction(self, "LibUsb_Exit")
        self.UsbConnTest = _FakeFunction(self, "UsbConnTest")
        self.dacwrite = _FakeFunction(self, "dacwrite")
        self.setuseroffset = _FakeFunction(self, "setuseroffset")
        self.start_tstd_mmf_usb = _FakeFunction(self, "start_tstd_mmf_usb")
        self.get_tstd_mmf_usb_data = _FakeFunction(
            self, "get_tstd_mmf_usb_data", self._read
        )
        self.stop_tstd_mmf_usb = _FakeFunction(self, "stop_tstd_mmf_usb")
        self.close_tstd_mmf = _FakeFunction(
            self, "close_tstd_mmf", lambda: None
        )

    def _read(self, max_bytes, destination):
        if not self.chunks:
            return 0
        data = self.chunks.popleft()
        if len(data) > max_bytes:
            raise AssertionError("fake data exceeds requested buffer")
        ctypes.memmove(destination, data, len(data))
        return len(data)

    def call_names(self):
        return [name for name, _ in self.calls]


class SerutekTimestampDecoderTest(unittest.TestCase):
    def test_decodes_signed_timestamp_channels_and_byte_carry(self):
        decoder = SerutekTimestampDecoder()
        payload = _raw_bytes(
            _raw_record(6, -2000),
            _raw_record(1, 100),
        )

        t1, c1 = decoder.feed(payload[:11])
        t2, c2 = decoder.feed(payload[11:])
        decoder.finish()

        np.testing.assert_array_equal(t1, np.array([0], dtype=np.int64))
        np.testing.assert_array_equal(c1, np.array([5], dtype=np.int64))
        np.testing.assert_array_equal(t2, np.array([2100], dtype=np.int64))
        np.testing.assert_array_equal(c2, np.array([0], dtype=np.int64))

    def test_unwraps_signed_57_bit_rollover(self):
        decoder = SerutekTimestampDecoder()
        times, channels = decoder.feed(
            _raw_bytes(
                _raw_record(1, SERUTEK_TIMESTAMP_SIGN - 2),
                _raw_record(2, -SERUTEK_TIMESTAMP_SIGN + 3),
            )
        )
        np.testing.assert_array_equal(times, np.array([0, 5], dtype=np.int64))
        np.testing.assert_array_equal(channels, np.array([0, 1], dtype=np.int64))

    def test_filters_invalid_channel_and_reports_trailing_bytes(self):
        decoder = SerutekTimestampDecoder()
        times, channels = decoder.feed(
            _raw_bytes(_raw_record(0, 10), _raw_record(1, 20)) + b"x"
        )
        np.testing.assert_array_equal(times, np.array([0], dtype=np.int64))
        np.testing.assert_array_equal(channels, np.array([0], dtype=np.int64))
        self.assertEqual(decoder.invalid_channel_records, 1)
        with self.assertRaises(SerutekDataError):
            decoder.finish()


class SerutekDLLTest(unittest.TestCase):
    def test_binds_and_validates_channel_configuration(self):
        library = _FakeLibrary()
        driver = SerutekDLL(library=library)
        driver.initialize()
        self.assertTrue(driver.connection_test())
        driver.set_threshold_mv(5, 4096)
        driver.set_offset_ps(0, -2000)
        driver.exit()

        self.assertEqual(
            library.call_names(),
            ["LibUsb_Init", "UsbConnTest", "dacwrite", "setuseroffset", "LibUsb_Exit"],
        )
        with self.assertRaises(ValueError):
            driver.set_threshold_mv(0, 4097)
        with self.assertRaises(ValueError):
            driver.set_offset_ps(6, 0)


class SerutekRegistryTest(unittest.TestCase):
    def test_serutek_is_lazy_registered_with_hardware_defaults(self):
        self.assertEqual(
            CLI_SOURCE_PLUGINS["serutek"],
            "pytimetag.device.SerutekTimeTag",
        )
        defaults = get_cli_source_defaults("serutek")
        self.assertEqual(defaults["channel_count"], 6)
        self.assertEqual(defaults["hardware_buffer_size"], 4 * 1024 * 1024)
        self.assertEqual(defaults["hardware_poll_s"], 0.2)


class SerutekTimeTagDeviceTest(unittest.TestCase):
    def _make_device(self, chunks, callback):
        library = _FakeLibrary(chunks)
        driver = SerutekDLL(library=library)
        device = SerutekTimeTag(
            serial_number="USB0",
            dataUpdate=callback,
            n_max_events=32,
            poll_interval_s=0.001,
            driver=driver,
        )
        return device, library

    def test_streams_packed_words_and_cleans_up_in_required_order(self):
        received = []
        ready = threading.Event()

        def callback(words):
            received.append(words)
            ready.set()

        device, library = self._make_device(
            [
                _raw_bytes(
                    _raw_record(1, 1000),
                    _raw_record(2, 2000),
                )
            ],
            callback,
        )
        try:
            device.start()
            self.assertTrue(ready.wait(1.0))
            device.stop()
        finally:
            device.close()

        words = np.concatenate(received)
        times, channels = unpack_timetag(words)
        np.testing.assert_array_equal(times, np.array([0, 1000], dtype=np.int64))
        np.testing.assert_array_equal(channels, np.array([0, 1], dtype=np.int64))

        names = library.call_names()
        self.assertLess(names.index("LibUsb_Init"), names.index("start_tstd_mmf_usb"))
        self.assertLess(names.index("stop_tstd_mmf_usb"), names.index("close_tstd_mmf"))
        self.assertLess(names.index("close_tstd_mmf"), names.index("LibUsb_Exit"))
        self.assertEqual(names.count("LibUsb_Init"), 1)
        self.assertEqual(names.count("LibUsb_Exit"), 1)

    def test_disabled_channel_is_filtered_locally(self):
        received = []
        ready = threading.Event()

        def callback(words):
            received.append(words)
            ready.set()

        device, _ = self._make_device(
            [_raw_bytes(_raw_record(1, 100), _raw_record(2, 200))],
            callback,
        )
        try:
            device.set_channel(1, enabled=False)
            device.start()
            self.assertTrue(ready.wait(1.0))
            device.stop()
        finally:
            device.close()

        _, channels = unpack_timetag(np.concatenate(received))
        np.testing.assert_array_equal(channels, np.array([0], dtype=np.int64))

    def test_general_deadtime_is_explicitly_unsupported(self):
        device, _ = self._make_device([], lambda words: None)
        try:
            with self.assertRaises(NotImplementedError):
                device.set_deadtime(0, 20e-9)
        finally:
            device.close()

    def test_gui_settings_allow_live_threshold_and_enabled_updates(self):
        device, library = self._make_device([], lambda words: None)
        try:
            device.start()
            device.set_channel(0, threshold_voltage=0.75, enabled=False)
            settings = device.get_channel_settings(0)
            self.assertEqual(settings["threshold_voltage"], 0.75)
            self.assertFalse(settings["enabled"])
            self.assertFalse(settings["supports_dead_time"])
            self.assertTrue(device.is_running())
            with self.assertRaisesRegex(SerutekError, "Stop SeruTek acquisition"):
                device.set_channel(0, offset_ps=10)
            device.stop()
        finally:
            device.close()

        self.assertIn("dacwrite", library.call_names())


if __name__ == "__main__":
    unittest.main()
