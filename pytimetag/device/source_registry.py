"""Maps CLI ``--source`` names to plugin modules (imported on demand)."""

from __future__ import annotations

import importlib
from typing import Dict, List

# Non-simulator sources: name -> import path (module is loaded only when selected).
CLI_SOURCE_PLUGINS: Dict[str, str] = {
    "swabian": "pytimetag.device.sources.swabian",
}


def list_cli_hardware_sources() -> List[str]:
    return sorted(CLI_SOURCE_PLUGINS.keys())


def import_cli_plugin(source: str):
    """Import the plugin module for *source* (e.g. ``swabian``)."""
    path = CLI_SOURCE_PLUGINS.get(source)
    if not path:
        raise KeyError(f"Unknown hardware source: {source!r}")
    return importlib.import_module(path)
