import argparse
import os
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.live import Live
from rich.table import Table

from pytimetag.analysers.CounterAnalyser import CounterAnalyser
from pytimetag.analysers.HistogramAnalyser import HistogramAnalyser
from pytimetag.datablock import DataBlock
from pytimetag.device import TimeTagSimulator, device_type_manager
from pytimetag.device.datablock_packer import (
    DataBlockPackerPath,
    DataBlockStreamPacker,
    SplitByChannelEvent,
    SplitByTimeWindow,
)
from pytimetag.device.source_registry import list_cli_hardware_sources


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


def _ensure_output_path(base_dir: Path, block: DataBlock) -> Path:
    dt = datetime.fromtimestamp(block.creationTime / 1000.0)
    date_dir = dt.strftime("%Y-%m-%d")
    hour_dir = dt.strftime("%H")
    save_dir = base_dir / date_dir / hour_dir
    os.makedirs(save_dir, exist_ok=True)
    name = dt.strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3] + ".datablock"
    return save_dir / name


def _build_block_count_table(
    block: DataBlock,
    seq: int,
    channel_count: int,
    output_path: Path = None,
    operation_timings: List[Tuple[str, Optional[float]]] = None,
    errors: List[str] = None,
) -> Table:
    table = Table(
        title=f"DataBlock #{seq}",
        show_header=True,
        header_style="bold cyan",
        expand=False,
    )
    table.add_column("Channel")
    table.add_column("Count", justify="right")
    table.add_column("Operation")
    table.add_column("Time (ms)", justify="right")
    op_rows = operation_timings[:] if operation_timings else []
    total_count = 0
    for ch in range(channel_count):
        cnt = block.sizes[ch]
        c = int(cnt)
        total_count += c
        if op_rows:
            op_name, op_ms = op_rows.pop(0)
            if op_name in ("analyser:", "analysers:"):
                time_text = ""
            elif op_ms is None:
                time_text = "disabled"
            else:
                time_text = f"{op_ms:.3f}"
            table.add_row(str(ch), f"{c:,}", op_name, time_text)
        else:
            table.add_row(str(ch), f"{c:,}", "", "")
    if op_rows:
        op_name, op_ms = op_rows.pop(0)
        if op_name in ("analyser:", "analysers:"):
            time_text = ""
        elif op_ms is None:
            time_text = "disabled"
        else:
            time_text = f"{op_ms:.3f}"
        table.add_row("TOTAL", f"{total_count:,}", op_name, time_text, style="bold green")
    else:
        table.add_row("TOTAL", f"{total_count:,}", "", "", style="bold green")
    for op_name, op_ms in op_rows:
        if op_name in ("analyser:", "analysers:"):
            time_text = ""
        elif op_ms is None:
            time_text = "disabled"
        else:
            time_text = f"{op_ms:.3f}"
        table.add_row("", "", op_name, time_text)
    if errors:
        for err in errors:
            table.add_row("", "", f"[red]{err}[/red]", "")
    if output_path is None:
        table.caption = "Storage: disabled"
    else:
        table.caption = f"Stored: {output_path}"
    return table


def main() -> None:
    source_choices = ["simulator"] + list_cli_hardware_sources()
    parser = argparse.ArgumentParser(
        description="Run a TimeTag app with the simulator or a registered hardware source, "
        "split into DataBlocks, show counts with a live table, and serialize blocks.",
        epilog="With no arguments, only this help is shown; specify at least --source or other options to run.",
    )
    parser.add_argument(
        "--source",
        default="simulator",
        choices=source_choices,
        help="Data source type (default: %(default)s when any argument is given)",
    )
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
    parser.add_argument(
        "--post-process",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable/disable post-processing analysers (default: enabled)",
    )
    parser.add_argument("--serial", default=None, help="Hardware device serial (when using a hardware --source)")
    parser.add_argument("--seed", type=int, default=42, help="Simulator RNG seed")
    parser.add_argument("--update-lo-s", type=float, default=0.05, help="Simulator update interval lower bound")
    parser.add_argument("--update-hi-s", type=float, default=0.10, help="Simulator update interval upper bound")
    parser.add_argument(
        "--hardware-buffer-size",
        type=int,
        default=int(1e6),
        dest="hardware_buffer_size",
        help="Hardware stream buffer size (n_max_events; meaning depends on --source plugin)",
    )
    parser.add_argument(
        "--hardware-poll-s",
        type=float,
        default=0.002,
        dest="hardware_poll_s",
        help="Hardware poll interval in seconds (meaning depends on --source plugin)",
    )
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
    if len(sys.argv) <= 1:
        parser.print_help()
        print(
            "\n提示：未提供任何参数，未启动采集。请至少指定 --source（例如 simulator 或 swabian）或 "
            "其它选项（如 --save）；见上文说明。\n",
        )
        raise SystemExit(0)
    args = parser.parse_args()

    console = Console(file=sys.stdout, force_terminal=True)
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
    worker_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="post-process")
    io_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="save-datablock")
    pending_futures: List[Future] = []
    registered_analysers: List[Tuple[str, object]] = [
        ("CounterAnalyser", CounterAnalyser()),
        ("HistogramAnalyser", HistogramAnalyser(args.channel_count)),
    ]
    for analyser_name, analyser in registered_analysers:
        if analyser_name == "CounterAnalyser":
            analyser.turnOn()
    latest_table = Table(title="Waiting for first DataBlock...", show_header=False)
    latest_table.add_column("Status")
    latest_table.add_row("Running...")

    def _serialize_block(block: DataBlock) -> Tuple[bytes, float]:
        start = time.perf_counter()
        payload = block.serialize()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return payload, elapsed_ms

    def _save_block_file(path: Path, payload: bytes) -> float:
        start = time.perf_counter()
        path.write_bytes(payload)
        return (time.perf_counter() - start) * 1000.0

    def _process_and_render_block(block: DataBlock, seq: int, out_path: Path, live: Live) -> None:
        operation_timings: List[Tuple[str, Optional[float]]] = []
        analyser_timings: List[Tuple[str, float]] = []
        errors: List[str] = []
        payload: bytes = b""
        payload_ready = False
        serialize_ms: float = None
        save_ms: float = None

        if args.save:
            try:
                payload, serialize_ms = _serialize_block(block)
                payload_ready = True
            except BaseException as e:
                errors.append(f"serialize failed: {e}")

        save_future: Future = None
        if args.save and out_path is not None and payload_ready:
            try:
                save_future = io_pool.submit(_save_block_file, out_path, payload)
            except BaseException as e:
                errors.append(f"schedule save failed: {e}")

        for analyser_name, analyser in registered_analysers:
            if args.post_process and analyser.isTurnedOn():
                start = time.perf_counter()
                try:
                    analyser.dataIncome(block)
                except BaseException as e:
                    errors.append(f"{analyser_name} failed: {e}")
                finally:
                    analyser_timings.append((f"  {analyser_name}", (time.perf_counter() - start) * 1000.0))
            else:
                analyser_timings.append((f"  {analyser_name}", None))

        if save_future is not None:
            try:
                save_ms = save_future.result()
            except BaseException as e:
                errors.append(f"save failed: {e}")

        if args.save:
            operation_timings.append(("serialize", serialize_ms))
            operation_timings.append(("storage", save_ms))
        else:
            operation_timings.append(("serialize", None))
            operation_timings.append(("storage", None))
        operation_timings.append(("analysers:", None))
        operation_timings.extend(analyser_timings)

        table = _build_block_count_table(
            block,
            seq,
            args.channel_count,
            out_path,
            operation_timings=operation_timings,
            errors=errors,
        )
        with render_lock:
            live.update(table, refresh=True)

    def handle_block(block: DataBlock, live: Live) -> None:
        nonlocal block_seq
        block_seq += 1
        out_path = _ensure_output_path(output_base, block) if args.save else None
        pending_futures.append(worker_pool.submit(_process_and_render_block, block, block_seq, out_path, live))

    def on_words(words, live: Live) -> None:
        produced = packer.feed_from_packed(words)
        for _, blocks in produced.items():
            for b in blocks:
                handle_block(b, live)

    console.print(
        f"[bold]TimeTag app started (source=[cyan]{args.source}[/cyan]). Press Ctrl+C to stop.[/bold]"
    )
    if args.save:
        console.print(f"Output directory: [cyan]{output_base}[/cyan]")
    else:
        console.print("Output directory: [dim]disabled (use --save to enable)[/dim]")
    if args.post_process:
        analyser_names = ", ".join(name for name, _ in registered_analysers)
        console.print(f"PostProcess: [green]enabled[/green] ({analyser_names})")
    else:
        console.print("PostProcess: [dim]disabled[/dim]")
    console.print(f"Split mode: [cyan]{args.split_mode}[/cyan] ({split_desc}), resolution: [cyan]{args.resolution}s/tick[/cyan]")
    with Live(
        latest_table,
        console=console,
        refresh_per_second=8,
        redirect_stdout=False,
        redirect_stderr=False,
    ) as live:
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
            device = device_type_manager.create_device_for_cli_source(
                args.source, args, console, live, on_words
            )
            if device is None:
                return

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
            for future in pending_futures:
                try:
                    future.result()
                except BaseException:
                    pass
            worker_pool.shutdown(wait=True)
            io_pool.shutdown(wait=True)
            console.print("[bold green]Stopped.[/bold green]")


if __name__ == "__main__":
    main()
