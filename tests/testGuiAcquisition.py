import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np

from pytimetag.datablock import DataBlock
from pytimetag.device.Simulator import pack_timetag
from pytimetag.device.datablock_packer import SplitByTimeWindow
from pytimetag.gui.acquisition import AcquisitionService
from pytimetag.gui.config import StreamPathConfig


class GuiAcquisitionRateTest(unittest.TestCase):
    def test_raw_storage_path_uses_computer_local_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AcquisitionService(
                stream_paths=[
                    StreamPathConfig(
                        name="test",
                        storage_db=str(root / "test.duckdb"),
                        datablock_dir=str(root / "blocks"),
                    )
                ],
                channel_count=1,
                resolution=1e-12,
                split=SplitByTimeWindow(int(1e12)),
                metrics_cb=lambda payload: None,
                log_cb=lambda level, message: None,
            )
            block = DataBlock(1_786_185_833_658, 0, 1, [0])
            local_time = datetime(2026, 8, 8, 18, 43, 53, 658000)

            with patch("pytimetag.gui.acquisition.datetime") as mocked_datetime:
                mocked_datetime.fromtimestamp.return_value = local_time
                output = service._ensure_output_path(block, root / "blocks")

            mocked_datetime.fromtimestamp.assert_called_once_with(
                block.creationTime / 1000.0
            )
            self.assertEqual(
                output,
                root
                / "blocks"
                / "2026-08-08"
                / "18"
                / "2026-08-08_18-43-53-658.datablock",
            )
            for path in service._paths.values():
                path["conn"].close()

    def test_storage_stream_includes_data_duration_for_rate_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emitted = []
            service = AcquisitionService(
                stream_paths=[
                    StreamPathConfig(
                        name="test",
                        storage_db=str(root / "test.duckdb"),
                        datablock_dir=str(root / "blocks"),
                    )
                ],
                channel_count=1,
                resolution=1e-12,
                split=SplitByTimeWindow(int(1e12)),
                metrics_cb=lambda payload: None,
                log_cb=lambda level, message: None,
                storage_stream_cb=emitted.append,
            )
            service.start()

            # Exactly 100 events/s for three seconds. Crossing each one-second
            # boundary emits the preceding complete DataBlock.
            ticks = np.arange(0, int(3e12), int(1e10), dtype=np.int64)
            channels = np.zeros(ticks.size, dtype=np.int64)
            service._on_words(pack_timetag(ticks, channels))
            service.stop()

            self.assertGreaterEqual(len(emitted), 2)
            for payload in emitted[:2]:
                self.assertEqual(payload["CounterAnalyser"]["0"], 100)
                self.assertEqual(payload["DurationSeconds"], 1.0)

            for path in service._paths.values():
                path["conn"].close()

    def test_raw_storage_can_be_enabled_while_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blocks_dir = root / "blocks"
            service = AcquisitionService(
                stream_paths=[
                    StreamPathConfig(
                        name="test",
                        storage_db=str(root / "test.duckdb"),
                        datablock_dir=str(blocks_dir),
                    )
                ],
                channel_count=1,
                resolution=1e-12,
                split=SplitByTimeWindow(int(1e12)),
                metrics_cb=lambda payload: None,
                log_cb=lambda level, message: None,
            )
            service.start()
            self.assertFalse(service.get_raw_storage_enabled())
            service.set_raw_storage_enabled(True)

            ticks = np.arange(0, int(2e12), int(1e10), dtype=np.int64)
            channels = np.zeros(ticks.size, dtype=np.int64)
            service._on_words(pack_timetag(ticks, channels))
            service.stop()

            self.assertTrue(service.get_raw_storage_enabled())
            self.assertGreaterEqual(len(list(blocks_dir.rglob("*.datablock"))), 1)
            for path in service._paths.values():
                path["conn"].close()


if __name__ == "__main__":
    unittest.main()
