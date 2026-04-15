"""Device instance manager for multi-instance device management.

Each instance is identified by a unique key: "{device_type}:{serial_number}"
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from pytimetag.device.base import DeviceInfo, TimeTagDevice
from pytimetag.device.datablock_packer import (
    DataBlockPackerPath,
    DataBlockStreamPacker,
    SplitByChannelEvent,
    SplitByTimeWindow,
)
from pytimetag.device.manager import device_type_manager
from pytimetag.device.Simulator import MAX_PACKED_CHANNELS, TimeTagSimulator
from pytimetag.device.SwabianSimulator import SwabianSimulator

DEVICE_LIMITS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "simulator": {
        "threshold_voltage": (-5.0, 5.0),
        "dead_time_s": (10e-9, 200e-9),
    },
    "swabian_simulator": {
        "threshold_voltage": (-2.0, 2.0),
        "dead_time_s": (5e-9, 500e-9),
    },
}


class DeviceInstance:
    """Wrapper for a running device instance with its metadata."""

    def __init__(
        self,
        device_type: str,
        serial_number: str,
        device: TimeTagDevice,
        model_name: Optional[str] = None,
    ):
        self.device_type = device_type
        self.serial_number = serial_number
        self.device = device
        self.model_name = model_name
        self._created_at = threading.current_thread().ident

    @property
    def unique_id(self) -> str:
        return f"{self.device_type}:{self.serial_number}"

    @property
    def manufacturer(self) -> str:
        if self.device_type == "simulator":
            return "Simulator"
        if self.device_type == "swabian_simulator":
            return "Swabian"
        if self.model_name:
            return self.model_name
        return self.device_type

    def to_dict(self) -> Dict[str, Any]:
        """Serialize instance metadata (not the device itself)."""
        running = False
        checker = getattr(self.device, "is_running", None)
        if callable(checker):
            try:
                running = bool(checker())
            except BaseException:
                running = False
        return {
            "device_type": self.device_type,
            "manufacturer": self.manufacturer,
            "serial_number": self.serial_number,
            "model_name": self.model_name,
            "unique_id": self.unique_id,
            "channel_count": self.device.channel_count,
            "resolution": self.device.resolution,
            "running": running,
        }


class DeviceInstanceManager:
    """Manages multiple running device instances.

    Each instance is keyed by "{device_type}:{serial_number}" to ensure uniqueness.
    """

    def __init__(self):
        self._instances: Dict[str, DeviceInstance] = {}
        self._lock = threading.RLock()

    def get_channel_limits(self, device_type: str) -> Dict[str, Tuple[float, float]]:
        return DEVICE_LIMITS.get(
            device_type,
            {
                "threshold_voltage": (-2.0, 2.0),
                "dead_time_s": (0.0, 1e-3),
            },
        )

    def list_instances(self) -> List[Dict[str, Any]]:
        """List all running device instances."""
        with self._lock:
            return [instance.to_dict() for instance in self._instances.values()]

    def get_instance(self, device_type: str, serial_number: str) -> Optional[DeviceInstance]:
        """Get a device instance by type and serial number."""
        key = f"{device_type}:{serial_number}"
        with self._lock:
            return self._instances.get(key)

    def create_simulator(
        self,
        serial_number: str = "SIMULATOR",
        channel_count: int = 16,
        data_callback: Optional[Callable[[np.ndarray], None]] = None,
        split: Optional[Union[SplitByTimeWindow, SplitByChannelEvent]] = None,
    ) -> DeviceInstance:
        """Create a standard 16-channel simulator instance.

        Args:
            serial_number: Unique serial for this simulator instance
            channel_count: Number of channels (default 16)
            data_callback: Optional callback for data updates
            split: DataBlock split policy for count-rate calculation
        """
        key = f"simulator:{serial_number}"

        with self._lock:
            if key in self._instances:
                raise ValueError(f"Simulator instance '{serial_number}' already exists")

            if data_callback is None:
                data_callback = lambda x: None

            if split is None:
                split = SplitByTimeWindow(int(1e12))

            packer = DataBlockStreamPacker(
                [DataBlockPackerPath("stream", split, channel_count=MAX_PACKED_CHANNELS, resolution=1e-12)]
            )

            device = TimeTagSimulator(
                dataUpdate=data_callback,
                channel_count=channel_count,
            )
            device.serial_number = serial_number
            device._update_chunk_count_rates = False
            device._channel_count_rates = [0.0] * channel_count

            def _wrapped_callback(words: np.ndarray) -> None:
                data_callback(words)
                produced = packer.feed_from_packed(words)
                for blocks in produced.values():
                    for block in blocks:
                        duration_ticks = getattr(block, "duration_ticks", block.dataTimeEnd - block.dataTimeBegin)
                        duration_s = max(duration_ticks * block.resolution, 1e-15)
                        for ch_idx in range(min(len(block.sizes), channel_count)):
                            device._channel_count_rates[ch_idx] = int(block.sizes[ch_idx] / duration_s)

            device._dataUpdate = _wrapped_callback

            original_start = device.start
            original_stop = device.stop

            def _wrapped_start() -> None:
                packer.reset()
                original_start()

            def _wrapped_stop() -> None:
                original_stop()
                packer.flush()
                for i in range(channel_count):
                    device._channel_count_rates[i] = 0.0

            device.start = _wrapped_start
            device.stop = _wrapped_stop

            device.set_channel(
                0,
                mode="Period",
                period_count=5_000,
                dead_time_s=10e-9,
                threshold_voltage=0.5,
                reference_pulse_v=1.0,
            )
            for ch_idx in range(1, device.channel_count):
                device.set_channel(
                    ch_idx,
                    mode="Random",
                    random_count=50_000,
                    dead_time_s=10e-9,
                    threshold_voltage=0.5,
                    reference_pulse_v=1.0,
                )

            instance = DeviceInstance(
                device_type="simulator",
                serial_number=serial_number,
                device=device,
                model_name="TimeTagSimulator",
            )

            self._instances[key] = instance
            return instance

    def create_swabian_simulator(
        self,
        serial_number: str = "SWABIAN-001",
        data_callback: Optional[Callable[[np.ndarray], None]] = None,
        split: Optional[Union[SplitByTimeWindow, SplitByChannelEvent]] = None,
    ) -> DeviceInstance:
        """Create a Swabian-style 8-channel simulator instance.

        Args:
            serial_number: Unique serial for this swabian simulator instance
            data_callback: Optional callback for data updates
            split: DataBlock split policy for count-rate calculation
        """
        key = f"swabian_simulator:{serial_number}"

        with self._lock:
            if key in self._instances:
                raise ValueError(f"Swabian simulator instance '{serial_number}' already exists")

            if data_callback is None:
                data_callback = lambda x: None

            if split is None:
                split = SplitByTimeWindow(int(1e12))

            channel_count = 8
            packer = DataBlockStreamPacker(
                [DataBlockPackerPath("stream", split, channel_count=MAX_PACKED_CHANNELS, resolution=1e-12)]
            )

            device = SwabianSimulator(
                dataUpdate=data_callback,
                serial_number=serial_number,
            )
            device._update_chunk_count_rates = False
            device._channel_count_rates = [0.0] * channel_count

            def _wrapped_callback(words: np.ndarray) -> None:
                data_callback(words)
                produced = packer.feed_from_packed(words)
                for blocks in produced.values():
                    for block in blocks:
                        duration_ticks = getattr(block, "duration_ticks", block.dataTimeEnd - block.dataTimeBegin)
                        duration_s = max(duration_ticks * block.resolution, 1e-15)
                        for ch_idx in range(min(len(block.sizes), channel_count)):
                            device._channel_count_rates[ch_idx] = int(block.sizes[ch_idx] / duration_s)

            device._dataUpdate = _wrapped_callback

            original_start = device.start
            original_stop = device.stop

            def _wrapped_start() -> None:
                packer.reset()
                original_start()

            def _wrapped_stop() -> None:
                original_stop()
                packer.flush()
                for i in range(channel_count):
                    device._channel_count_rates[i] = 0.0

            device.start = _wrapped_start
            device.stop = _wrapped_stop

            device.set_channel(
                0,
                mode="Period",
                period_count=5_000,
                dead_time_s=5e-9,
                threshold_voltage=0.5,
                reference_pulse_v=1.0,
            )
            for ch_idx in range(1, device.channel_count):
                device.set_channel(
                    ch_idx,
                    mode="Random",
                    random_count=50_000,
                    dead_time_s=5e-9,
                    threshold_voltage=0.5,
                    reference_pulse_v=1.0,
                )

            instance = DeviceInstance(
                device_type="swabian_simulator",
                serial_number=serial_number,
                device=device,
                model_name="SwabianSimulator",
            )

            self._instances[key] = instance
            return instance

    def start_instance(self, device_type: str, serial_number: str) -> None:
        """Start a device instance."""
        instance = self.get_instance(device_type, serial_number)
        if instance is None:
            raise ValueError(f"Device instance '{device_type}:{serial_number}' not found")
        instance.device.start()

    def stop_instance(self, device_type: str, serial_number: str) -> None:
        """Stop a device instance."""
        instance = self.get_instance(device_type, serial_number)
        if instance is None:
            raise ValueError(f"Device instance '{device_type}:{serial_number}' not found")
        instance.device.stop()

    def remove_instance(self, device_type: str, serial_number: str) -> None:
        """Stop and remove a device instance."""
        key = f"{device_type}:{serial_number}"
        with self._lock:
            instance = self._instances.get(key)
            if instance is None:
                raise ValueError(f"Device instance '{key}' not found")

            instance.device.stop()
            del self._instances[key]

    def get_channel_info(
        self, device_type: str, serial_number: str
    ) -> List[Dict[str, Any]]:
        """Get channel information for a device instance.

        Returns list of channel info dicts with:
        - channel_id: int
        - dead_time_s: float
        - threshold_voltage: float
        - enabled: bool
        - mode: str (for simulator)
        """
        instance = self.get_instance(device_type, serial_number)
        if instance is None:
            raise ValueError(f"Device instance '{device_type}:{serial_number}' not found")

        device = instance.device
        limits = self.get_channel_limits(instance.device_type)
        channels = []

        count_rates = []
        if hasattr(device, "get_channel_count_rates"):
            try:
                count_rates = device.get_channel_count_rates()  # type: ignore[attr-defined]
            except BaseException:
                pass

        for ch_idx in range(device.channel_count):
            ch_info: Dict[str, Any] = {
                "channel_id": ch_idx,
            }

            # Prefer querying settings from device implementation directly.
            if hasattr(device, "get_channel_settings"):
                try:
                    settings = device.get_channel_settings(ch_idx)  # type: ignore[attr-defined]
                    if isinstance(settings, dict):
                        ch_info.update(settings)
                except BaseException:
                    pass

            # Backward compatibility for simulator-style implementations.
            if "dead_time_s" not in ch_info or "threshold_voltage" not in ch_info:
                if isinstance(device, (TimeTagSimulator, SwabianSimulator)):
                    ch = device.channel(ch_idx)
                    ch_info.update({
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
                    })
                else:
                    ch_info.update({
                        "dead_time_s": ch_info.get("dead_time_s", 0.0),
                        "threshold_voltage": ch_info.get("threshold_voltage", 0.0),
                        "enabled": ch_info.get("enabled", True),
                        "mode": ch_info.get("mode"),
                    })

            ch_info.update(
                {
                    "threshold_voltage_range": list(limits["threshold_voltage"]),
                    "dead_time_s_range": list(limits["dead_time_s"]),
                }
            )

            if isinstance(count_rates, (list, tuple)) and ch_idx < len(count_rates):
                ch_info["count_rate"] = float(count_rates[ch_idx])

            channels.append(ch_info)

        return channels

    def set_channel_config(
        self,
        device_type: str,
        serial_number: str,
        channel_id: int,
        config: Dict[str, Any],
    ) -> None:
        """Set channel configuration for a device instance.

        Args:
            device_type: Device type
            serial_number: Device serial number
            channel_id: Channel index
            config: Configuration dict with optional keys:
                - dead_time_s: float
                - threshold_voltage: float
                - enabled: bool
                - mode: str
                - period_count: int
                - random_count: int
        """
        instance = self.get_instance(device_type, serial_number)
        if instance is None:
            raise ValueError(f"Device instance '{device_type}:{serial_number}' not found")

        device = instance.device

        if channel_id < 0 or channel_id >= device.channel_count:
            raise ValueError(f"Channel {channel_id} out of range (0-{device.channel_count-1})")

        limits = self.get_channel_limits(instance.device_type)
        if "dead_time_s" in config:
            dead_time_s = float(config["dead_time_s"])
            low, high = limits["dead_time_s"]
            if dead_time_s < low or dead_time_s > high:
                raise ValueError(f"dead_time_s out of range [{low}, {high}]")
        if "threshold_voltage" in config:
            threshold_voltage = float(config["threshold_voltage"])
            low, high = limits["threshold_voltage"]
            if threshold_voltage < low or threshold_voltage > high:
                raise ValueError(f"threshold_voltage out of range [{low}, {high}]")

        # Handle simulator-specific settings (both Simulator and SwabianSimulator)
        if isinstance(device, (TimeTagSimulator, SwabianSimulator)):
            ch = device.channel(channel_id)

            # Update allowed fields
            allowed_fields = {
                "dead_time_s", "threshold_voltage", "enabled", "mode",
                "period_count", "random_count", "pulse_count", "pulse_events",
                "pulse_sigma_s", "reference_pulse_v",
            }

            for key, value in config.items():
                if key in allowed_fields and hasattr(ch, key):
                    setattr(ch, key, value)
        else:
            # For other devices, use base device methods
            if "dead_time_s" in config:
                device.set_deadtime(channel_id, config["dead_time_s"])
            if "threshold_voltage" in config:
                device.set_trigger_level(channel_id, config["threshold_voltage"])


# Global instance manager
instance_manager = DeviceInstanceManager()
