__author__ = 'Hwaipy'

import threading
import time
import unittest

import numpy as np

from pytimetag.datablock import DataBlock
from pytimetag.device.Simulator import (
    DEFAULT_CHANNEL_COUNT,
    MAX_PACKED_CHANNELS,
    ChannelSettings,
    TimeTagSimulator,
    pack_timetag,
    unpack_timetag,
)


class SimulatorTest(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)

    def test_pack_unpack_roundtrip(self):
        t = np.array([1234567890123456], dtype=np.int64)
        ch = np.array([11], dtype=np.int64)
        w = pack_timetag(t, ch)
        self.assertEqual(w.dtype, np.uint64)
        t2, ch2 = unpack_timetag(w)
        np.testing.assert_array_equal(t2, t)
        np.testing.assert_array_equal(ch2, ch)

    def test_pack_unpack_batch_matches_reference(self):
        """Pack matches NumPy bitwise formula; unpack matches per-word Python semantics (lossy for some int64)."""
        rng = np.random.default_rng(0)
        ticks = rng.integers(-(2**59), 2**59, size=500, dtype=np.int64)
        chans = rng.integers(0, 16, size=500, dtype=np.int64)
        words = pack_timetag(ticks, chans)
        words_ref = (ticks.astype(np.uint64) << np.uint64(4)) | (chans.astype(np.uint64) & np.uint64(15))
        np.testing.assert_array_equal(words, words_ref)
        ut, uc = unpack_timetag(words)
        for i in range(words.size):
            wi = int(np.uint64(words[i]))
            ch_r = wi & 0xF
            t_u = wi >> 4
            if t_u >= 2**63:
                t_r = t_u - 2**64
            else:
                t_r = t_u
            self.assertEqual(int(uc[i]), ch_r)
            self.assertEqual(int(ut[i]), t_r)

    def test_pack_channel_range(self):
        with self.assertRaises(ValueError):
            pack_timetag(np.array([0], dtype=np.int64), np.array([16], dtype=np.int64))

    def test_pack_requires_ndarray(self):
        with self.assertRaises(TypeError):
            pack_timetag(1, np.array([0], dtype=np.int64))
        with self.assertRaises(TypeError):
            pack_timetag(np.array([0], dtype=np.int64), 1)

    def test_pack_requires_matching_shape(self):
        with self.assertRaises(ValueError):
            pack_timetag(np.zeros(3, dtype=np.int64), np.zeros(4, dtype=np.int64))
        with self.assertRaises(ValueError):
            pack_timetag(np.zeros((2, 3), dtype=np.int64), np.zeros((3, 2), dtype=np.int64))

    def test_unpack_requires_ndarray(self):
        w = pack_timetag(np.array([1], dtype=np.int64), np.array([0], dtype=np.int64))
        with self.assertRaises(TypeError):
            unpack_timetag([int(w[0])])
        with self.assertRaises(TypeError):
            unpack_timetag(int(w[0]))

    def test_channel_count_default(self):
        batches = []

        def cb(arr):
            batches.append(arr)

        sim = TimeTagSimulator(cb)
        self.assertEqual(sim.channel_count, DEFAULT_CHANNEL_COUNT)
        self.assertEqual(DEFAULT_CHANNEL_COUNT, 16)

    def test_channel_count_custom_and_max_pack(self):
        batches = []

        sim = TimeTagSimulator(lambda a: batches.append(a), channel_count=4)
        self.assertEqual(sim.channel_count, 4)
        with self.assertRaises(IndexError):
            sim.channel(4)

    def test_channel_count_too_many_for_pack(self):
        with self.assertRaises(ValueError):
            TimeTagSimulator(lambda _: None, channel_count=MAX_PACKED_CHANNELS + 1)

    def test_channel_count_invalid(self):
        with self.assertRaises(ValueError):
            TimeTagSimulator(lambda _: None, channel_count=0)

    def test_channel_index_bounds(self):
        sim = TimeTagSimulator(lambda _: None, channel_count=8)
        with self.assertRaises(IndexError):
            sim.channel(-1)
        with self.assertRaises(IndexError):
            sim.channel(8)

    def test_set_channel_unknown_field(self):
        sim = TimeTagSimulator(lambda _: None)
        with self.assertRaises(TypeError):
            sim.set_channel(0, not_a_field=1)

    def test_step_period_stream(self):
        received = []

        def cb(arr):
            received.append(arr.copy())

        span = int(round(1.0 / 1e-12))
        sim = TimeTagSimulator(
            cb,
            resolution=1e-12,
            update_interval_range_s=(1.0, 1.0),
            realtime_pacing=False,
        )
        sim.set_channel(
            0,
            mode='Period',
            period_count=100,
            dead_time_s=0.0,
            threshold_voltage=0.0,
            reference_pulse_v=1.0,
        )
        sim.step()
        self.assertEqual(len(received), 1)
        arr = received[0]
        self.assertEqual(arr.dtype, np.uint64)
        self.assertEqual(arr.size, 100)
        times, channels = unpack_timetag(arr)
        self.assertTrue(np.all(channels == 0))
        self.assertTrue(np.all(times[:-1] <= times[1:]))
        self.assertGreaterEqual(int(times.min()), 0)
        self.assertLessEqual(int(times.max()), span)

    def test_disabled_and_reset(self):
        received = []

        sim = TimeTagSimulator(
            lambda a: received.append(a.copy()),
            update_interval_range_s=(1.0, 1.0),
            realtime_pacing=False,
        )
        sim.set_channel(3, mode='Period', period_count=50, enabled=False)
        sim.step()
        _, chs_arr = unpack_timetag(received[-1])
        chs = set(chs_arr.tolist())
        self.assertNotIn(3, chs)
        sim.reset_channels()
        sim.set_channel(3, mode='Period', period_count=10, enabled=True, threshold_voltage=-1.0, reference_pulse_v=1.0)
        sim.step()
        _, chs2 = unpack_timetag(received[-1])
        n3 = int(np.sum(chs2 == 3))
        self.assertEqual(n3, 10)

    def test_dead_time_reduces_events(self):
        received = []
        span = int(round(1e-3 / 1e-12))
        sim = TimeTagSimulator(
            lambda a: received.append(a.copy()),
            resolution=1e-12,
            update_interval_range_s=(1e-3, 1e-3),
            realtime_pacing=False,
        )
        # 1 ms window → 1000 events at 1 MHz
        sim.set_channel(0, mode='Period', period_count=1_000_000, dead_time_s=0.0, threshold_voltage=-1.0, reference_pulse_v=1.0)
        sim.step()
        _, c_full = unpack_timetag(received[-1])
        n_full = int(np.sum(c_full == 0))
        sim.set_channel(0, mode='Period', period_count=1_000_000, dead_time_s=2e-6, threshold_voltage=-1.0, reference_pulse_v=1.0)
        sim.step()
        _, c_dt = unpack_timetag(received[-1])
        n_dt = int(np.sum(c_dt == 0))
        self.assertEqual(n_full, 1000)
        self.assertLess(n_dt, n_full)
        self.assertGreater(n_dt, 200)

    def test_threshold_blocks_when_above_reference(self):
        received = []
        sim = TimeTagSimulator(
            lambda a: received.append(a.copy()),
            update_interval_range_s=(1.0, 1.0),
            realtime_pacing=False,
        )
        sim.set_channel(
            0,
            mode='Period',
            period_count=500,
            dead_time_s=0.0,
            threshold_voltage=1.5,
            reference_pulse_v=0.5,
        )
        sim.step()
        _, c0 = unpack_timetag(received[-1])
        n0 = int(np.sum(c0 == 0))
        self.assertEqual(n0, 0)

    def test_random_mode_sorted(self):
        np.random.seed(7)
        received = []
        sim = TimeTagSimulator(
            lambda a: received.append(a.copy()),
            update_interval_range_s=(1.0, 1.0),
            realtime_pacing=False,
        )
        sim.set_channel(
            1,
            mode='Random',
            random_count=2000,
            dead_time_s=0.0,
            threshold_voltage=-0.5,
            reference_pulse_v=1.0,
        )
        sim.step()
        arr = received[-1]
        times, chans = unpack_timetag(arr)
        t1 = times[chans == 1]
        self.assertEqual(t1.size, 2000)
        self.assertTrue(all(t1[i] <= t1[i + 1] for i in range(len(t1) - 1)))

    def test_pulse_mode_alias(self):
        np.random.seed(99)
        received = []
        sim = TimeTagSimulator(
            lambda a: received.append(a.copy()),
            update_interval_range_s=(1.0, 1.0),
            realtime_pacing=False,
        )
        sim.set_channel(
            2,
            mode='RandomPulse',
            pulse_count=5000,
            pulse_events=800,
            pulse_sigma_s=50e-12,
            dead_time_s=0.0,
            threshold_voltage=0.0,
            reference_pulse_v=1.0,
        )
        sim.step()
        _, cc = unpack_timetag(received[-1])
        n2 = int(np.sum(cc == 2))
        self.assertEqual(n2, 800)

    def test_background_thread_delivers(self):
        received = []

        def cb(arr):
            received.append(arr.size)

        sim = TimeTagSimulator(
            cb,
            update_interval_range_s=(0.0025, 0.0025),
            seed=0,
        )
        sim.set_channel(0, mode='Period', period_count=4000, threshold_voltage=-1.0, reference_pulse_v=1.0)
        sim.start()
        time.sleep(0.05)
        sim.stop()
        self.assertGreater(len(received), 0)
        self.assertTrue(all(n == 10 for n in received))

    def test_channel_settings_generate_tuple(self):
        self.assertIsNone(ChannelSettings(mode=None).to_generate_tuple())
        self.assertEqual(
            ChannelSettings(mode='Period', period_count=3).to_generate_tuple(),
            ('Period', 3),
        )
        self.assertEqual(
            ChannelSettings(mode='Random', random_count=5).to_generate_tuple(),
            ('Random', 5),
        )
        res = 1e-12
        t = ChannelSettings(mode='Pulse', pulse_count=10, pulse_events=4, pulse_sigma_s=1.2 * res).to_generate_tuple(
            resolution=res
        )
        self.assertEqual(t[0], 'Pulse')
        self.assertEqual(t[1], 10)
        self.assertEqual(t[2], 4)
        self.assertAlmostEqual(t[3], 1.2)

    def test_detection_keep_probability(self):
        ch = ChannelSettings(threshold_voltage=0.2, reference_pulse_v=1.0)
        self.assertAlmostEqual(ch.detection_keep_probability(), 1.0)
        ch2 = ChannelSettings(threshold_voltage=1.0, reference_pulse_v=1.0)
        self.assertAlmostEqual(ch2.detection_keep_probability(), 0.0)

    def test_data_update_must_be_callable(self):
        with self.assertRaises(TypeError):
            TimeTagSimulator(None)

    def test_lab_window_matches_wall_interval(self):
        """Δt_real / resolution == simulated [begin, end) width in ticks (same draw as pacing window)."""
        mins = []

        def cb(arr):
            if arr.size == 0:
                return
            times, _ = unpack_timetag(arr)
            mins.append(int(times.min()))

        dt = 1e-9
        sim = TimeTagSimulator(
            cb,
            resolution=1e-12,
            update_interval_range_s=(dt, dt),
            seed=0,
        )
        # ~3 events in 1 ns ⇒ ~3e9 Hz
        sim.set_channel(0, mode='Period', period_count=3_000_000_000, threshold_voltage=-1.0, reference_pulse_v=1.0)
        sim.step()
        sim.step()
        span_ticks = int(round(dt / 1e-12))
        self.assertEqual(span_ticks, 1000)
        self.assertGreaterEqual(mins[1] - mins[0], span_ticks - 1)

    def test_period_hz_global_grid_across_batches(self):
        """Period mode keeps a fixed tick grid; consecutive 1 s batches touch at multiples of P."""
        received = []

        sim = TimeTagSimulator(
            lambda a: received.append(a.copy()),
            resolution=1e-12,
            update_interval_range_s=(1.0, 1.0),
            seed=1,
            realtime_pacing=False,
        )
        sim.set_channel(0, mode='Period', period_count=10, threshold_voltage=-1.0, reference_pulse_v=1.0)
        sim.step()
        sim.step()
        t1, _ = unpack_timetag(received[0])
        t2, _ = unpack_timetag(received[1])
        P = int(round(1.0 / (10.0 * 1e-12)))
        self.assertTrue(np.all(t1 % P == 0))
        self.assertTrue(np.all(t2 % P == 0))
        self.assertEqual(int(t2.min()), int(t1.max()) + P)

    def test_integration_long_run_monotonic_and_datablock_stats(self):
        """
        Run the simulator ~2.5 s wall time with 50–80 ms steps, merge batches, check global time
        order, build a :class:`DataBlock`, and sanity-check Period / Random / Pulse behaviour.

        ``DataBlock.dataTimeBegin`` / ``dataTimeEnd`` are **host clock** bounds for the acquisition
        window (ms), not the min/max of timetag values in ``content``; lab-time extent is asserted
        separately from the packed stream.
        """
        batches = []
        first_batch_done = threading.Event()
        resolution = 1e-12
        period_hz = 200
        random_hz = 50_000

        def append_batch(arr):
            batches.append(arr.copy())
            first_batch_done.set()

        sim = TimeTagSimulator(
            append_batch,
            channel_count=4,
            resolution=resolution,
            seed=123,
            update_interval_range_s=(0.05, 0.08),
        )
        sim.set_channel(0, mode='Period', period_count=period_hz, threshold_voltage=-1.0, reference_pulse_v=1.0)
        sim.set_channel(1, mode='Random', random_count=random_hz, threshold_voltage=-1.0, reference_pulse_v=1.0)
        sim.set_channel(
            2,
            mode='Pulse',
            pulse_count=200,
            pulse_events=60,
            pulse_sigma_s=100e-12,
            threshold_voltage=-1.0,
            reference_pulse_v=1.0,
        )

        wall_begin_ms = time.time() * 1000
        sim.start()
        # Avoid a scheduler race on busy CI: main may sleep/stop before the worker runs once.
        self.assertTrue(
            first_batch_done.wait(timeout=30.0),
            'simulator thread should call dataUpdate at least once (check start() / thread failure)',
        )
        time.sleep(2.5)
        sim.stop()
        wall_end_ms = time.time() * 1000

        self.assertGreater(len(batches), 15, 'expected many batches over ~2.5 s wall time after first batch')
        stream = np.concatenate(batches)
        self.assertGreater(stream.size, 5000)

        times, chans = unpack_timetag(stream)
        self.assertTrue(
            bool(np.all(times[1:] >= times[:-1])),
            'concatenated batches must be globally non-decreasing in lab time',
        )

        t_begin = int(times.min())
        t_end_excl = int(times.max()) + 1
        lab_duration_s = (t_end_excl - t_begin) * resolution
        self.assertGreater(lab_duration_s, 2.2, 'lab time should track ~wall time')
        self.assertLess(lab_duration_s, 2.95)

        content = []
        for c in range(4):
            tc = times[chans == c]
            self.assertTrue(bool(np.all(tc[:-1] <= tc[1:])), 'per-channel times must be sorted')
            content.append(np.asarray(tc, dtype=np.int64))

        db = DataBlock.create(content, time.time() * 1000, t_begin, t_end_excl, resolution=resolution)
        self.assertIsNotNone(db.content)
        self.assertEqual(db.dataTimeBegin, t_begin)
        self.assertEqual(db.dataTimeEnd, t_end_excl)

        P = int(round(1.0 / (period_hz * resolution)))
        tc0 = db.content[0]
        self.assertGreater(tc0.size, 100)
        self.assertTrue(bool(np.all(tc0 % P == 0)), 'Period channel should sit on the global Hz grid')
        d0 = np.diff(tc0.astype(np.int64))
        self.assertTrue(bool(np.all(d0 >= P)), 'Period spacings are multiples of the grid step P')

        tc1 = db.content[1]
        self.assertGreater(tc1.size, 5000)
        mid = 0.5 * (t_begin + t_end_excl)
        half_span = 0.5 * (t_end_excl - t_begin)
        self.assertLess(abs(float(tc1.mean()) - mid), 0.12 * half_span, 'Random times should center on window')
        nb = 12
        hist, _ = np.histogram(tc1, bins=nb, range=(t_begin, t_end_excl))
        expected = tc1.size / nb
        chi2 = float(np.sum((hist - expected) ** 2 / np.maximum(expected, 1.0)))
        self.assertLess(chi2, 35.0, 'histogram should be roughly uniform (chi-square on bins)')

        tc2 = db.content[2]
        n_batches = len(batches)
        self.assertGreater(tc2.size, int(0.7 * 60 * n_batches))
        self.assertLess(tc2.size, int(1.3 * 60 * n_batches))

if __name__ == '__main__':
    unittest.main()
