__author__ = 'Hwaipy'

import unittest
import numpy as np
from pytimetag.datablock import DataBlock
from pytimetag.device.Simulator import pack_timetag
from pytimetag.device.datablock_packer import (
    DataBlockPackerPath,
    DataBlockStreamPacker,
    SplitByChannelEvent,
    SplitByTimeWindow,
    feed_callback_for_simulator,
    pack_timestamps_channels_to_content,
)


def _events_from_data_block(db: DataBlock):
    """(time_tick, channel_index) pairs sorted by time then channel."""
    pairs = []
    for ci, arr in enumerate(db.content):
        if arr is None or len(arr) == 0:
            continue
        for t in np.asarray(arr, dtype=np.int64).ravel():
            pairs.append((int(t), ci))
    pairs.sort(key=lambda x: (x[0], x[1]))
    return pairs


class DataBlockPackerTest(unittest.TestCase):
    def test_init_requires_non_empty_paths(self):
        with self.assertRaises(ValueError):
            DataBlockStreamPacker([])

    def test_init_requires_unique_path_names(self):
        with self.assertRaises(ValueError):
            DataBlockStreamPacker(
                [
                    DataBlockPackerPath('a', SplitByTimeWindow(10)),
                    DataBlockPackerPath('a', SplitByTimeWindow(20)),
                ]
            )

    def test_feed_requires_matching_shapes(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('x', SplitByTimeWindow(100))])
        with self.assertRaises(ValueError):
            p.feed(np.zeros(3, dtype=np.int64), np.zeros(4, dtype=np.int64))

    def test_split_by_time_window_closes_block_when_boundary_crossed(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(100))])
        ts = np.array([0, 40, 80, 100, 120], dtype=np.int64)
        ch = np.array([0, 0, 0, 0, 0], dtype=np.int64)
        r = p.feed(ts, ch)
        self.assertIn('w', r)
        self.assertEqual(len(r['w']), 1)
        db = r['w'][0]
        self.assertEqual(db.dataTimeBegin, 0)
        self.assertEqual(db.dataTimeEnd, 80)
        ev = _events_from_data_block(db)
        self.assertEqual(ev, [(0, 0), (40, 0), (80, 0)])
        tail = p.flush()['w'][0]
        self.assertEqual(_events_from_data_block(tail), [(100, 0), (120, 0)])

    def test_split_by_time_window_multiple_blocks_in_one_feed(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(100))])
        ts = np.array([0, 50, 100, 150, 200, 250], dtype=np.int64)
        ch = np.zeros(6, dtype=np.int64)
        r = p.feed(ts, ch)
        self.assertEqual(len(r['w']), 2)
        self.assertEqual(_events_from_data_block(r['w'][0]), [(0, 0), (50, 0)])
        self.assertEqual(_events_from_data_block(r['w'][1]), [(100, 0), (150, 0)])
        rest = p.flush()['w'][0]
        self.assertEqual(_events_from_data_block(rest), [(200, 0), (250, 0)])

    def test_split_by_time_window_accumulates_across_feed_calls(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(100))])
        self.assertNotIn('w', p.feed(np.array([0, 40], dtype=np.int64), np.zeros(2, dtype=np.int64)))
        r = p.feed(np.array([90, 100], dtype=np.int64), np.zeros(2, dtype=np.int64))
        self.assertIn('w', r)
        self.assertEqual(len(r['w']), 1)
        self.assertEqual(
            _events_from_data_block(r['w'][0]),
            [(0, 0), (40, 0), (90, 0)],
        )

    def test_channel_filter_keeps_only_listed_channels(self):
        p = DataBlockStreamPacker(
            [DataBlockPackerPath('w', SplitByTimeWindow(50), channels=(0, 2))]
        )
        ts = np.array([0, 10, 20, 30, 60], dtype=np.int64)
        ch = np.array([0, 1, 2, 1, 0], dtype=np.int64)
        r = p.feed(ts, ch)
        db = r['w'][0]
        ev = _events_from_data_block(db)
        self.assertEqual(ev, [(0, 0), (20, 2)])
        self.assertEqual(db.sizes[1], 0)

    def test_split_by_channel_edge_excludes_trigger_from_block(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('c', SplitByChannelEvent(2))])
        ts = np.array([10, 20, 30, 40], dtype=np.int64)
        ch = np.array([0, 0, 2, 0], dtype=np.int64)
        r = p.feed(ts, ch)
        self.assertEqual(len(r['c']), 1)
        self.assertEqual(_events_from_data_block(r['c'][0]), [(10, 0), (20, 0)])
        tail = p.flush()['c'][0]
        self.assertEqual(_events_from_data_block(tail), [(30, 2), (40, 0)])

    def test_split_by_channel_edge_leading_trigger_waits_for_second(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('c', SplitByChannelEvent(2))])
        self.assertEqual(
            p.feed(np.array([5], dtype=np.int64), np.array([2], dtype=np.int64)),
            {},
        )
        r = p.feed(
            np.array([10, 15], dtype=np.int64),
            np.array([0, 2], dtype=np.int64),
        )
        self.assertEqual(len(r['c']), 1)
        self.assertEqual(_events_from_data_block(r['c'][0]), [(5, 2), (10, 0)])
        tail = p.flush()['c'][0]
        self.assertEqual(_events_from_data_block(tail), [(15, 2)])

    def test_flush_emits_incomplete_time_window(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(10**18))])
        ts = np.array([1, 2, 3], dtype=np.int64)
        ch = np.array([0, 1, 2], dtype=np.int64)
        self.assertEqual(p.feed(ts, ch), {})
        f = p.flush()
        self.assertEqual(len(f['w']), 1)
        self.assertEqual(sum(f['w'][0].sizes), 3)

    def test_reset_clears_internal_buffers(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(10**18))])
        p.feed(np.array([1], dtype=np.int64), np.array([0], dtype=np.int64))
        p.reset()
        self.assertEqual(p.flush(), {})

    def test_two_paths_independent_in_one_feed(self):
        p = DataBlockStreamPacker(
            [
                DataBlockPackerPath('time', SplitByTimeWindow(100), channels=(0, 1)),
                DataBlockPackerPath('edge', SplitByChannelEvent(2)),
            ]
        )
        ts = np.array([0, 10, 50, 99, 100, 150], dtype=np.int64)
        ch = np.array([0, 1, 0, 0, 0, 2], dtype=np.int64)
        r = p.feed(ts, ch)
        self.assertIn('time', r)
        self.assertIn('edge', r)
        self.assertEqual(sum(r['edge'][0].sizes), 5)
        self.assertEqual(r['edge'][0].sizes[2], 0)

    def test_resolution_passed_to_data_block(self):
        p = DataBlockStreamPacker(
            [DataBlockPackerPath('w', SplitByTimeWindow(10), resolution=2e-12)]
        )
        ts = np.array([0, 5, 20], dtype=np.int64)
        ch = np.zeros(3, dtype=np.int64)
        db = p.feed(ts, ch)['w'][0]
        self.assertEqual(db.resolution, 2e-12)

    def test_invalid_time_window_raises(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(0))])
        with self.assertRaises(ValueError):
            p.feed(np.array([0, 1], dtype=np.int64), np.zeros(2, dtype=np.int64))

    def test_invalid_split_channel_raises(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('c', SplitByChannelEvent(16))])
        with self.assertRaises(ValueError):
            p.feed(np.array([0], dtype=np.int64), np.array([0], dtype=np.int64))

    def test_wrong_channel_count_in_path_raises(self):
        with self.assertRaises(ValueError):
            DataBlockStreamPacker(
                [DataBlockPackerPath('x', SplitByTimeWindow(10), channel_count=8)]
            )

    def test_feed_from_packed_matches_feed_after_unpack(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(50))])
        ts = np.array([0, 10, 60], dtype=np.int64)
        ch = np.array([0, 1, 0], dtype=np.int64)
        words = pack_timetag(ts, ch)
        r1 = p.feed(ts, ch)
        p2 = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(50))])
        r2 = p2.feed_from_packed(words)
        self.assertEqual(len(r1['w']), len(r2['w']))
        self.assertEqual(_events_from_data_block(r1['w'][0]), _events_from_data_block(r2['w'][0]))

    def test_feed_callback_for_simulator(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(100))])
        seen = []

        def on_block(name, db):
            seen.append((name, sum(db.sizes)))

        cb = feed_callback_for_simulator(p, on_block)
        cb(pack_timetag(np.array([0, 50, 150], dtype=np.int64), np.zeros(3, dtype=np.int64)))
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], 'w')
        self.assertEqual(seen[0][1], 2)

        cb2 = feed_callback_for_simulator(p, None)
        cb2(pack_timetag(np.array([200], dtype=np.int64), np.zeros(1, dtype=np.int64)))
        self.assertEqual(len(seen), 1)

    def test_pack_timestamps_channels_to_content_merges_sections(self):
        c = pack_timestamps_channels_to_content(
            [np.array([10, 30], dtype=np.int64), np.array([20], dtype=np.int64)],
            [np.array([0, 1], dtype=np.int64), np.array([0], dtype=np.int64)],
        )
        self.assertEqual(len(c), 16)
        np.testing.assert_array_equal(c[0], np.array([10, 20], dtype=np.int64))
        np.testing.assert_array_equal(c[1], np.array([30], dtype=np.int64))

    def test_pack_timestamps_channels_to_content_section_mismatch(self):
        with self.assertRaises(ValueError):
            pack_timestamps_channels_to_content([np.array([1], dtype=np.int64)], [])

    def test_empty_chunk_no_crash(self):
        p = DataBlockStreamPacker([DataBlockPackerPath('w', SplitByTimeWindow(10))])
        self.assertEqual(p.feed(np.array([], dtype=np.int64), np.array([], dtype=np.int64)), {})


if __name__ == '__main__':
    unittest.main()
