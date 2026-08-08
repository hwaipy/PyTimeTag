import os
import unittest
from unittest.mock import patch

from pytimetag.device.instance_manager import DeviceInstanceManager
from pytimetag.gui.config import GuiConfig


class _FakeHardwareDevice:
    def __init__(self):
        self.channel_count = 6
        self.resolution = 1e-12
        self.running = False
        self.closed = False
        self.channel_updates = []

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def close(self):
        self.closed = True

    def is_running(self):
        return self.running

    def set_channel(self, channel, **config):
        self.channel_updates.append((channel, config))

    def set_deadtime(self, channel, dead_time_s):
        raise AssertionError("SeruTek dead time must not be called in this test")


class SerutekGuiConfigTest(unittest.TestCase):
    def test_serutek_hardware_options_load_from_environment(self):
        values = {
            "PYTIMETAG_DEVICE_TYPE": "serutek",
            "PYTIMETAG_DEVICE_SERIAL": "USB0",
            "PYTIMETAG_DEVICE_CHANNEL_COUNT": "6",
            "PYTIMETAG_DEVICE_DRIVER_PATH": r"C:\SeruTek\Tdc_Libusb_Dll.dll",
            "PYTIMETAG_HARDWARE_BUFFER_SIZE": "4194304",
            "PYTIMETAG_HARDWARE_POLL_S": "0.2",
        }
        with patch.dict(os.environ, values, clear=False):
            config = GuiConfig.from_env()

        self.assertEqual(config.device_type, "serutek")
        self.assertEqual(config.device_serial, "USB0")
        self.assertEqual(config.device_channel_count, 6)
        self.assertEqual(config.device_driver_path, values["PYTIMETAG_DEVICE_DRIVER_PATH"])
        self.assertEqual(config.hardware_buffer_size, 4 * 1024 * 1024)
        self.assertEqual(config.hardware_poll_s, 0.2)


class SerutekInstanceManagerTest(unittest.TestCase):
    def test_creates_controls_and_closes_serutek_hardware(self):
        manager = DeviceInstanceManager()
        device = _FakeHardwareDevice()

        with patch(
            "pytimetag.device.instance_manager.import_cli_plugin"
        ) as import_plugin, patch(
            "pytimetag.device.instance_manager.device_type_manager.connect",
            return_value=device,
        ) as connect:
            instance = manager.create_hardware_device(
                "serutek",
                "USB0",
                6,
                model_name="HSPCL6",
                n_max_events=4 * 1024 * 1024,
                poll_interval_s=0.2,
                dll_path=r"C:\SeruTek\Tdc_Libusb_Dll.dll",
            )

        import_plugin.assert_called_once_with("serutek")
        self.assertEqual(connect.call_args.args[0], "serutek")
        self.assertEqual(connect.call_args.kwargs["serial_number"], "USB0")
        self.assertEqual(connect.call_args.kwargs["channel_count"], 6)
        self.assertEqual(instance.to_dict()["manufacturer"], "SeruTek")
        self.assertEqual(instance.to_dict()["model_name"], "HSPCL6")

        manager.start_instance("serutek", "USB0")
        self.assertTrue(device.running)
        manager.set_channel_config(
            "serutek",
            "USB0",
            2,
            {"threshold_voltage": 0.75, "enabled": False},
        )
        self.assertEqual(
            device.channel_updates,
            [(2, {"threshold_voltage": 0.75, "enabled": False})],
        )

        manager.remove_instance("serutek", "USB0")
        self.assertFalse(device.running)
        self.assertTrue(device.closed)
        self.assertIsNone(manager.get_instance("serutek", "USB0"))


if __name__ == "__main__":
    unittest.main()
