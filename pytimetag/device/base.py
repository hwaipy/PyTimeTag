from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np


@dataclass(frozen=True)
class DeviceInfo:
    """Runtime-discovered hardware entry."""

    device_type: str
    serial_number: str
    model_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TimeTagDevice(ABC):
    """
    Unified time-tag source interface.

    Implementations must emit packed uint64 words (low 4 bits = channel 0..15, upper bits = time tick)
    via the callback provided at construction.
    """

    def __init__(
        self,
        dataUpdate: Callable[[np.ndarray], None],
        channel_count: int = 16,
        resolution: float = 1e-12,
        serial_number: Optional[str] = None,
    ):
        if not callable(dataUpdate):
            raise TypeError("dataUpdate must be callable")
        if channel_count < 1:
            raise ValueError("channel_count must be >= 1")
        self._dataUpdate = dataUpdate
        self._channel_count = int(channel_count)
        self.resolution = float(resolution)
        self.serial_number = serial_number

    @property
    def channel_count(self) -> int:
        return self._channel_count

    @abstractmethod
    def start(self) -> None:
        """Start acquisition."""

    @abstractmethod
    def stop(self) -> None:
        """Stop acquisition."""

    @abstractmethod
    def set_channel(self, index: int, **kwargs) -> None:
        """Configure one channel with implementation-specific fields."""

    @abstractmethod
    def set_deadtime(self, channel: int, dead_time_s: float) -> None:
        """Set per-channel dead time in seconds."""

    @abstractmethod
    def set_trigger_level(self, channel: int, trigger_level_v: float) -> None:
        """Set per-channel trigger threshold voltage."""


class TimeTagDeviceFactory(ABC):
    """Factory interface used by the device manager."""

    device_type: str = ""

    @classmethod
    @abstractmethod
    def discover(cls) -> List[DeviceInfo]:
        """Discover available devices of this type."""

    @classmethod
    @abstractmethod
    def connect(
        cls,
        serial_number: str,
        dataUpdate: Callable[[np.ndarray], None],
        **kwargs,
    ) -> TimeTagDevice:
        """Connect one device by serial number and return a running object."""
