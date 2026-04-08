from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from celery import shared_task

from pytimetag.datablock import DataBlock


@shared_task(name="pytimetag.gui.process_datablock")
def process_datablock(path: str) -> Dict[str, object]:
    target = Path(path)
    payload = target.read_bytes()
    block = DataBlock.deserialize(payload)
    total = int(sum(block.sizes))
    per_channel: List[int] = [int(x) for x in block.sizes]
    return {
        "path": str(target),
        "creation_time_ms": int(block.creationTime),
        "data_time_begin": int(block.dataTimeBegin),
        "data_time_end": int(block.dataTimeEnd),
        "resolution": float(block.resolution),
        "total_events": total,
        "per_channel_counts": per_channel,
    }

