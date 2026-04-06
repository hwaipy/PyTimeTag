from __future__ import annotations

from typing import Callable, Dict, List, Optional, Type

import numpy as np

from pytimetag.device.base import DeviceInfo, TimeTagDevice, TimeTagDeviceFactory


class DeviceTypeManager:
    """Registry for multiple time-tag hardware vendors."""

    def __init__(self):
        self._factories: Dict[str, Type[TimeTagDeviceFactory]] = {}

    def register(self, factory_cls: Type[TimeTagDeviceFactory]) -> None:
        device_type = getattr(factory_cls, "device_type", None)
        if not device_type:
            raise ValueError("factory_cls must provide a non-empty device_type")
        self._factories[str(device_type)] = factory_cls

    def registered_types(self) -> List[str]:
        return sorted(self._factories.keys())

    def discover(self, device_type: Optional[str] = None) -> List[DeviceInfo]:
        if device_type is not None:
            if device_type not in self._factories:
                raise KeyError(f"Unknown device type: {device_type}")
            return self._factories[device_type].discover()

        out: List[DeviceInfo] = []
        for name in self.registered_types():
            out.extend(self._factories[name].discover())
        return out

    def connect(
        self,
        device_type: str,
        serial_number: str,
        dataUpdate: Callable[[np.ndarray], None],
        **kwargs,
    ) -> TimeTagDevice:
        if device_type not in self._factories:
            raise KeyError(f"Unknown device type: {device_type}")
        return self._factories[device_type].connect(
            serial_number=serial_number,
            dataUpdate=dataUpdate,
            **kwargs,
        )


device_type_manager = DeviceTypeManager()
