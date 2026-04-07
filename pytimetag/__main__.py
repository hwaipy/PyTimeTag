import argparse
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from rich.console import Console
from rich.live import Live
from rich.table import Table

from pytimetag.datablock import DataBlock
from pytimetag.device import TimeTagSimulator, device_type_manager
from pytimetag.device.SwabianTimeTag import SwabianNumPyABIError
from pytimetag.device.datablock_packer import (
    DataBlockPackerPath,
    DataBlockStreamPacker,
    SplitByChannelEvent,
    SplitByTimeWindow,
)


def _parse_channel_settings(items: List[str], channel_count: int) -> Dict[int, Dict[str, object]]:
    """
    Parse repeated --channel items:
      INDEX:key=value,key=value
    Example:
      1:mode=Random,random_count=100000
      2:mode=Period,period_count=10,threshold_voltage=-0.2
    """
    settings: Dict[int, Dict[str, object]] = {}
    for raw in items:
        if ":" not in raw:
            raise ValueError(f"Invalid --channel format: {raw!r}. Expected INDEX:key=value,...")
        idx_str, body = raw.split(":", 1)
        idx = int(idx_str.strip())
        if idx < 0 or idx >= channel_count:
            raise ValueError(f"Channel index out of range: {idx}, valid 0..{channel_count - 1}")
        cfg: Dict[str, object] = {}
        if body.strip():
            for kv in body.split(","):
                if not kv.strip():
                    continue
                if "=" not in kv:
                    raise ValueError(f"Invalid channel setting item: {kv!r}, expected key=value")
                k, v = kv.split("=", 1)
                key = k.strip()
                val_raw = v.strip()
                if val_raw.lower() in ("true", "false"):
                    val: object = val_raw.lower() == "true"
                else:
                    try:
                        if "." in val_raw or "e" in val_raw.lower():
                            val = float(val_raw)
                            if isinstance(val, float) and val.is_integer():
                                val = int(val)
                        else:
                            val = int(val_raw)
                    except ValueError:
                        val = val_raw
                cfg[key] = val
        settings[idx] = cfg
    return settings


def _parse_channel_scalar(items: List[str], channel_count: int, option_name: str) -> Dict[int, float]:
    """
    Parse repeated per-channel scalar options in the form:
      INDEX:VALUE
    Example:
      1:0.2
      3:5e-08
    """
    out: Dict[int, float] = {}
    for raw in items:
        if ":" not in raw:
            raise ValueError(f"Invalid {option_name} format: {raw!r}. Expected INDEX:VALUE")
        idx_str, value_str = raw.split(":", 1)
        idx = int(idx_str.strip())
        if idx < 0 or idx >= channel_count:
            raise ValueError(f"Channel index out of range in {option_name}: {idx}, valid 0..{channel_count - 1}")
        out[idx] = float(value_str.strip())
    return out


def _print_swabian_numpy_abi_help(console: Console) -> None:
    """After a Swabian/NumPy ABI failure, print a short, actionable fix (no traceback)."""
    console.print()
    console.print("[bold red]Swabian TimeTagger / NumPy ABI mismatch[/bold red]")
    console.print(
        "The loaded Swabian driver was built for NumPy 1.x, but this environment has NumPy 2.x "
        "(or the reverse), so [cyan]_TimeTagger[/cyan] cannot load."
    )
    console.print()
    console.print("[bold]Option A — stay on NumPy 2.x[/bold] (upgrade the driver; try in order):")
    console.print("  [cyan]pip install -U \"Swabian-TimeTagger\"[/cyan]")
    console.print(
        "  Update the [cyan]Swabian Instruments Time Tagger[/cyan] desktop install to the latest version. "
        "If Python still imports [cyan]TimeTagger[/cyan] from [dim]Program Files[/dim], that copy may be older "
        "than the pip wheel; check Swabian’s docs for which path should win."
    )
    console.print()
    console.print("[bold]Option B — use NumPy 1.x in this environment[/bold] (works with older drivers):")
    console.print("  [cyan]pip install \"numpy>=1.25,<2\"[/cyan]")
    console.print()


def _discover_swabian_info(serial: str = None) -> Tuple[str, List[str]]:
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


def _ensure_output_path(base_dir: Path, block: DataBlock) -> Path:
    dt = datetime.fromtimestamp(block.creationTime / 1000.0)
    date_dir = dt.strftime("%Y-%m-%d")
    hour_dir = dt.strftime("%H")
    save_dir = base_dir / date_dir / hour_dir
    os.makedirs(save_dir, exist_ok=True)
    name = dt.strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3] + ".datablock"
    return save_dir / name


def _build_block_count_table(
    block: DataBlock, seq: int, channel_count: int, output_path: Path = None
) -> Table:
    table = Table(
        title=f"DataBlock #{seq}",
        show_header=True,
        header_style="bold cyan",
        expand=False,
    )
    table.add_column("Channel")
    table.add_column("Count", justify="right")
    total_count = 0
    for ch in range(channel_count):
        cnt = block.sizes[ch]
        c = int(cnt)
        total_count += c
        table.add_row(str(ch), f"{c:,}")
    table.add_row("TOTAL", f"{total_count:,}", style="bold green")
    if output_path is None:
        table.caption = "Storage: disabled"
    else:
        table.caption = f"Stored: {output_path}"
    return table


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a TimeTag app with Simulator or Swabian source, split into DataBlocks, show counts with rich live table, and serialize blocks."
    )
    parser.add_argument("--source", default="simulator", choices=["simulator", "swabian"], help="Data source type")
    parser.add_argument("--output-dir", default="./store_test", help="Directory used to store serialized DataBlocks")
    parser.add_argument("--save", action="store_true", help="Enable saving serialized DataBlocks to output-dir")
    parser.add_argument("--split-s", type=float, default=1.0, help="DataBlock split window in seconds (default: 1.0)")
    parser.add_argument(
        "--split-mode",
        choices=["time", "channel"],
        default="time",
        help="Split mode: time window or trigger channel event",
    )
    parser.add_argument("--split-channel", type=int, default=0, help="Trigger channel index for --split-mode channel")
    parser.add_argument("--channel-count", type=int, default=8, help="Active channel count used by source")
    parser.add_argument("--resolution", type=float, default=1e-12, help="Seconds per tick")
    parser.add_argument("--serial", default=None, help="Swabian device serial number")
    parser.add_argument("--seed", type=int, default=42, help="Simulator RNG seed")
    parser.add_argument("--update-lo-s", type=float, default=0.05, help="Simulator update interval lower bound")
    parser.add_argument("--update-hi-s", type=float, default=0.10, help="Simulator update interval upper bound")
    parser.add_argument("--swabian-buffer-size", type=int, default=int(1e6), help="Swabian TimeTagStream n_max_events")
    parser.add_argument("--swabian-poll-s", type=float, default=0.002, help="Swabian stream polling interval (seconds)")
    parser.add_argument(
        "--channel",
        action="append",
        default=[],
        help=(
            "Per-channel config; repeatable. Format: INDEX:key=value,key=value. "
            "Example: --channel '1:mode=Random,random_count=100000'"
        ),
    )
    parser.add_argument(
        "--trigger-level",
        action="append",
        default=[],
        help="Per-channel trigger voltage for hardware-like sources, format INDEX:V (repeatable).",
    )
    parser.add_argument(
        "--deadtime-s",
        action="append",
        default=[],
        help="Per-channel dead time in seconds for hardware-like sources, format INDEX:SECONDS (repeatable).",
    )
    args = parser.parse_args()

    console = Console()
    output_base = Path(args.output_dir).resolve()
    if args.save:
        output_base.mkdir(parents=True, exist_ok=True)

    if args.split_mode == "time":
        window_ticks = int(round(args.split_s / args.resolution))
        if window_ticks <= 0:
            raise ValueError("split window must map to at least 1 tick")
        split_cfg = SplitByTimeWindow(window_ticks)
        split_desc = f"time={args.split_s}s"
    else:
        if args.split_channel < 0 or args.split_channel >= 16:
            raise ValueError("--split-channel must be in 0..15")
        split_cfg = SplitByChannelEvent(args.split_channel)
        split_desc = f"channel={args.split_channel}"

    packer = DataBlockStreamPacker(
        [DataBlockPackerPath("stream", split_cfg, channel_count=16, resolution=args.resolution)]
    )

    block_seq = 0
    render_lock = threading.Lock()
    latest_table = Table(title="Waiting for first DataBlock...", show_header=False)
    latest_table.add_column("Status")
    latest_table.add_row("Running...")

    def handle_block(block: DataBlock, live: Live) -> None:
        nonlocal block_seq
        block_seq += 1
        out_path = None
        if args.save:
            out_path = _ensure_output_path(output_base, block)
            out_path.write_bytes(block.serialize())
        table = _build_block_count_table(block, block_seq, args.channel_count, out_path)
        with render_lock:
            live.update(table, refresh=True)

    def on_words(words, live: Live) -> None:
        produced = packer.feed_from_packed(words)
        for _, blocks in produced.items():
            for b in blocks:
                handle_block(b, live)

    source_label = "Simulator source" if args.source == "simulator" else "Swabian source"
    console.print(f"[bold]TimeTag app started ({source_label}). Press Ctrl+C to stop.[/bold]")
    if args.save:
        console.print(f"Output directory: [cyan]{output_base}[/cyan]")
    else:
        console.print("Output directory: [dim]disabled (use --save to enable)[/dim]")
    console.print(f"Split mode: [cyan]{args.split_mode}[/cyan] ({split_desc}), resolution: [cyan]{args.resolution}s/tick[/cyan]")
    with Live(latest_table, console=console, refresh_per_second=8) as live:
        channel_settings = _parse_channel_settings(args.channel, args.channel_count)
        trigger_levels = _parse_channel_scalar(args.trigger_level, args.channel_count, "--trigger-level")
        deadtimes = _parse_channel_scalar(args.deadtime_s, args.channel_count, "--deadtime-s")

        if args.source == "simulator":
            device = TimeTagSimulator(
                dataUpdate=lambda words: on_words(words, live),
                channel_count=args.channel_count,
                resolution=args.resolution,
                seed=args.seed,
                update_interval_range_s=(args.update_lo_s, args.update_hi_s),
                realtime_pacing=True,
            )

            # Default baseline config so users can run CLI without extra options.
            device.set_channel(0, mode="Period", period_count=1, threshold_voltage=-1.0, reference_pulse_v=1.0)
            for i in range(1, args.channel_count):
                device.set_channel(i, mode="Random", random_count=50_000, threshold_voltage=-1.0, reference_pulse_v=1.0)
        else:
            serial, available = _discover_swabian_info(args.serial)
            console.print(f"Swabian serial: [cyan]{serial}[/cyan] (available: {', '.join(available)})")
            device = device_type_manager.connect(
                "swabian",
                serial_number=serial,
                dataUpdate=lambda words: on_words(words, live),
                channel_count=args.channel_count,
                resolution=args.resolution,
                n_max_events=args.swabian_buffer_size,
                poll_interval_s=args.swabian_poll_s,
            )

        for idx, cfg in channel_settings.items():
            device.set_channel(idx, **cfg)
        for idx, v in trigger_levels.items():
            device.set_trigger_level(idx, float(v))
        for idx, dt in deadtimes.items():
            device.set_deadtime(idx, float(dt))

        device.start()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping...[/yellow]")
        finally:
            device.stop()
            if hasattr(device, "close"):
                try:
                    device.close()
                except BaseException:
                    pass
            tail = packer.flush()
            for _, blocks in tail.items():
                for b in blocks:
                    handle_block(b, live)
            console.print("[bold green]Stopped.[/bold green]")


if __name__ == "__main__":
    try:
        main()
    except SwabianNumPyABIError:
        _print_swabian_numpy_abi_help(Console(stderr=True))
        sys.exit(1)
