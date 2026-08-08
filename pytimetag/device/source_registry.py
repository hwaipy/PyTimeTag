"""Maps CLI ``--source`` names to plugin modules (imported on demand)."""

from __future__ import annotations

import importlib
from typing import Any, Dict, List

# Non-simulator sources: name -> import path (module is loaded only when selected).
CLI_SOURCE_PLUGINS: Dict[str, str] = {
    "serutek": "pytimetag.device.SerutekTimeTag",
    "swabian": "pytimetag.device.sources.swabian",
}

CLI_SOURCE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "serutek": {
        "channel_count": 6,
        "hardware_buffer_size": 4 * 1024 * 1024,
        "hardware_poll_s": 0.2,
        "serial_number": "USB0",
    },
    "swabian": {
        "channel_count": 8,
        "hardware_buffer_size": int(1e6),
        "hardware_poll_s": 0.002,
    },
}


def list_cli_hardware_sources() -> List[str]:
    return sorted(CLI_SOURCE_PLUGINS.keys())


def get_cli_source_defaults(source: str) -> Dict[str, Any]:
    """Return source-specific defaults without importing the hardware module."""
    return dict(CLI_SOURCE_DEFAULTS.get(source, {}))


def import_cli_plugin(source: str):
    """Import the plugin module for *source* (e.g. ``swabian``)."""
    path = CLI_SOURCE_PLUGINS.get(source)
    if not path:
        raise KeyError(f"Unknown hardware source: {source!r}")
    return importlib.import_module(path)
