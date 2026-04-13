"""Swabian Simulator - An 8-channel simulator mimicking Swabian TimeTagger behavior."""

from __future__ import annotations

from typing import Optional

from pytimetag.device.Simulator import TimeTagSimulator


class SwabianSimulator(TimeTagSimulator):
    """
    Swabian-style TimeTag simulator with 8 channels (default Swabian configuration).

    Inherits from TimeTagSimulator but defaults to:
    - 8 channels (instead of 16)
    - Serial number prefix "SWABIAN-"
    - Model name "SwabianSimulator"
    """

    def __init__(
        self,
        dataUpdate,
        serial_number: str = "SWABIAN-001",
        resolution: float = 1e-12,
        seed: Optional[int] = None,
        **kwargs,
    ):
        # Swabian devices typically have 8 channels
        super().__init__(
            dataUpdate=dataUpdate,
            channel_count=8,
            resolution=resolution,
            seed=seed,
            **kwargs,
        )
        self.serial_number = serial_number
        self._model_name = "SwabianSimulator"

    @property
    def model_name(self) -> str:
        return self._model_name
