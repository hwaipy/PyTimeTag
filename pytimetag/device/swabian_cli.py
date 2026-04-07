"""Swabian TimeTagger helpers for CLI: device discovery and NumPy ABI help text."""

from __future__ import annotations

from typing import List, Optional, Tuple

from rich.console import Console

from pytimetag.device.manager import device_type_manager
from pytimetag.device.SwabianTimeTag import (
    MIN_TIMETAGGER_VERSION_FOR_NUMPY2,
    SWABIAN_DOWNLOADS_URL,
    SWABIAN_NUMPY2_KB_URL,
    detect_swabian_timetagger_version,
    recommended_pip_command,
    recommended_python_m_pytimetag,
    timetagger_version_is_below_numpy2_support,
)


def print_swabian_numpy_abi_help(console: Console) -> None:
    """After a Swabian/NumPy ABI failure, print a short, actionable fix (no traceback)."""
    ver, src = detect_swabian_timetagger_version()
    below = timetagger_version_is_below_numpy2_support(ver)
    pip_upgrade = recommended_pip_command("install", "-U", "Swabian-TimeTagger")
    pip_upgrade_force = recommended_pip_command(
        "install", "--upgrade", "--force-reinstall", "--no-cache-dir", "Swabian-TimeTagger"
    )
    pip_numpy1 = recommended_pip_command("install", "numpy>=1.25,<2")
    run_example = recommended_python_m_pytimetag("--source", "swabian")

    console.print()
    console.print("[bold red]Swabian TimeTagger / NumPy ABI mismatch[/bold red]")
    console.print(
        "The [cyan]_TimeTagger[/cyan] native module does not match this environment’s NumPy (binary ABI). "
        f"Swabian documents NumPy ≥ 2 support from Time Tagger [cyan]{MIN_TIMETAGGER_VERSION_FOR_NUMPY2}[/cyan] onward; see: "
        f"[link={SWABIAN_NUMPY2_KB_URL}]Swabian KB[/link]"
    )
    console.print()
    if ver:
        console.print(f"Detected TimeTagger version: [cyan]{ver}[/cyan] (source: [dim]{src}[/dim])")
    else:
        console.print("Could [bold]not[/bold] detect the Swabian TimeTagger version (pip / TimeTagger.py).")
    console.print()

    console.print(
        f"[bold]Choice 1 — upgrade Time Tagger / driver[/bold] (needed if the install is older than "
        f"[cyan]{MIN_TIMETAGGER_VERSION_FOR_NUMPY2}[/cyan], or Python is loading an old copy from "
        f"[dim]Program Files\\…[/dim])"
    )
    if below is True:
        console.print(
            f"  Your reported version looks [yellow]below[/yellow] [cyan]{MIN_TIMETAGGER_VERSION_FOR_NUMPY2}[/cyan]. "
            f"Upgrade to [cyan]{MIN_TIMETAGGER_VERSION_FOR_NUMPY2}[/cyan] or newer (latest recommended)."
        )
    elif below is False:
        console.print(
            "  Your reported version is already at or above that release; if the error persists, "
            "another older [cyan]_TimeTagger[/cyan] may win import order over the pip wheel (check [dim]PYTHONPATH[/dim] "
            "and [dim]…\\\\Program Files\\\\…[/dim])."
        )
    else:
        console.print(
            f"  If this environment is older than [cyan]{MIN_TIMETAGGER_VERSION_FOR_NUMPY2}[/cyan], "
            "upgrade the desktop app and the Python package."
        )
    console.print("  [bold]Upgrade the pip package[/bold] (use this interpreter only; copy-paste as one line):")
    console.print(f"  [cyan]{pip_upgrade}[/cyan]")
    console.print("  If problems remain, force reinstall:")
    console.print(f"  [cyan]{pip_upgrade_force}[/cyan]")
    console.print(
        f"  [bold]Desktop installer:[/bold] [link={SWABIAN_DOWNLOADS_URL}]swabianinstruments.com/time-tagger/downloads[/link]"
    )
    console.print()

    console.print("[bold]Choice 2 — use NumPy 1.x in this environment[/bold] (works with older [cyan]_TimeTagger[/cyan] builds)")
    console.print("  [bold]Downgrade NumPy[/bold] (same interpreter as above):")
    console.print(f"  [cyan]{pip_numpy1}[/cyan]")
    console.print("  Then run again, e.g.:")
    console.print(f"  [cyan]{run_example}[/cyan]")
    console.print("  Use a separate virtualenv if other projects require NumPy 2.")
    console.print()


def discover_swabian_serial(serial: Optional[str] = None) -> Tuple[str, List[str]]:
    """
    Discover connected Swabian devices and return the chosen serial plus the full list.

    Raises ``RuntimeError`` if none or multiple devices when *serial* is required.
    """
    devices = device_type_manager.discover("swabian")
    if not devices:
        raise RuntimeError("No connected Swabian Time Tagger found.")
    serials = [d.serial_number for d in devices]
    if serial is None:
        if len(serials) > 1:
            raise RuntimeError(
                "Multiple Swabian devices found. Please specify --serial. "
                f"Available serials: {', '.join(serials)}"
            )
        return serials[0], serials
    if serial not in serials:
        raise RuntimeError(
            f"Requested --serial {serial!r} not found. Available serials: {', '.join(serials)}"
        )
    return serial, serials
