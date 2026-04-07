"""CLI plugin for the ``swabian`` hardware source (loaded only when ``--source swabian``)."""

from __future__ import annotations

from typing import Any, Callable, Optional

import numpy as np

from pytimetag.device.SwabianTimeTag import SwabianNumPyABIError
from pytimetag.device.swabian_cli import discover_swabian_serial, print_swabian_numpy_abi_help


def _ensure_factory_registered() -> None:
    # Import side effect: registers ``SwabianTimeTagFactory`` on ``device_type_manager``.
    import pytimetag.device.SwabianTimeTag  # noqa: F401


def create_device(
    manager: Any,
    args: Any,
    console: Any,
    live: Any,
    on_words: Callable[[np.ndarray, Any], None],
) -> Optional[Any]:
    """
    Build the device for ``--source swabian`` using *manager*.connect.

    Returns ``None`` if setup was aborted after printing help (e.g. NumPy ABI mismatch).
    """
    _ensure_factory_registered()
    try:
        serial, available = discover_swabian_serial(getattr(args, "serial", None))
        console.print(f"Device serial: [cyan]{serial}[/cyan] (available: {', '.join(available)})")
        return manager.connect(
            "swabian",
            serial_number=serial,
            dataUpdate=lambda words: on_words(words, live),
            channel_count=args.channel_count,
            resolution=args.resolution,
            n_max_events=getattr(args, "hardware_buffer_size", int(1e6)),
            poll_interval_s=getattr(args, "hardware_poll_s", 0.002),
        )
    except SwabianNumPyABIError:
        print_swabian_numpy_abi_help(console)
        return None
