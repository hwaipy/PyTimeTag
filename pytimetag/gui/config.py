from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class StreamPathConfig:
    name: str
    storage_db: str
    datablock_dir: str


@dataclass(frozen=True)
class GuiConfig:
    host: str = "127.0.0.1"
    port: int = 8787
    storage_db: str = "./store_test/pytimetag.duckdb"
    datablock_dir: str = "./store_test"
    celery_broker_url: str = "redis://127.0.0.1:6379/0"
    celery_result_backend: str = "redis://127.0.0.1:6379/1"
    serve_web: bool = True
    save_raw_data: bool = False
    stream_paths: List[StreamPathConfig] = field(default_factory=list)
    device_type: str = "simulator"
    device_serial: str = "simulator"
    device_channel_count: int = 16
    split_mode: str = "time"
    split_s: float = 1.0
    split_channel: int = 0

    @classmethod
    def from_env(cls) -> "GuiConfig":
        stream_paths: List[StreamPathConfig] = []
        paths_raw = os.getenv("PYTIMETAG_STREAM_PATHS", "").strip()
        if paths_raw:
            for segment in paths_raw.split(";"):
                segment = segment.strip()
                if not segment:
                    continue
                parts = segment.split(":")
                if len(parts) < 3:
                    continue
                name = parts[0].strip()
                db = parts[1].strip()
                raw_dir = ":".join(parts[2:]).strip()
                stream_paths.append(StreamPathConfig(name=name, storage_db=db, datablock_dir=raw_dir))
        return cls(
            host=os.getenv("PYTIMETAG_GUI_HOST", "127.0.0.1"),
            port=int(os.getenv("PYTIMETAG_GUI_PORT", "8787")),
            storage_db=os.getenv("PYTIMETAG_STORAGE_DB", "./store_test/pytimetag.duckdb"),
            datablock_dir=os.getenv("PYTIMETAG_DATABLOCK_DIR", "./store_test"),
            celery_broker_url=os.getenv("PYTIMETAG_CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"),
            celery_result_backend=os.getenv("PYTIMETAG_CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1"),
            serve_web=os.getenv("PYTIMETAG_GUI_SERVE_WEB", "1").strip().lower() not in ("0", "false", "no"),
            save_raw_data=os.getenv("PYTIMETAG_SAVE_RAW_DATA", "0").strip().lower() in ("1", "true", "yes"),
            stream_paths=stream_paths,
            device_type=os.getenv("PYTIMETAG_DEVICE_TYPE", "simulator"),
            device_serial=os.getenv("PYTIMETAG_DEVICE_SERIAL", "simulator"),
            device_channel_count=int(os.getenv("PYTIMETAG_DEVICE_CHANNEL_COUNT", "16")),
            split_mode=os.getenv("PYTIMETAG_SPLIT_MODE", "time"),
            split_s=float(os.getenv("PYTIMETAG_SPLIT_S", "1.0")),
            split_channel=int(os.getenv("PYTIMETAG_SPLIT_CHANNEL", "0")),
        )

    @property
    def storage_db_path(self) -> Path:
        return Path(self.storage_db).resolve()

    @property
    def datablock_dir_path(self) -> Path:
        return Path(self.datablock_dir).resolve()

    def resolved_stream_paths(self) -> List[StreamPathConfig]:
        if self.stream_paths:
            return list(self.stream_paths)
        return [
            StreamPathConfig(
                name="default",
                storage_db=self.storage_db,
                datablock_dir=self.datablock_dir,
            )
        ]
