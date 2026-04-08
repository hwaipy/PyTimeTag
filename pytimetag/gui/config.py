from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GuiConfig:
    host: str = "127.0.0.1"
    port: int = 8787
    storage_db: str = "./store_test/pytimetag.duckdb"
    datablock_dir: str = "./store_test"
    celery_broker_url: str = "redis://127.0.0.1:6379/0"
    celery_result_backend: str = "redis://127.0.0.1:6379/1"

    @classmethod
    def from_env(cls) -> "GuiConfig":
        return cls(
            host=os.getenv("PYTIMETAG_GUI_HOST", "127.0.0.1"),
            port=int(os.getenv("PYTIMETAG_GUI_PORT", "8787")),
            storage_db=os.getenv("PYTIMETAG_STORAGE_DB", "./store_test/pytimetag.duckdb"),
            datablock_dir=os.getenv("PYTIMETAG_DATABLOCK_DIR", "./store_test"),
            celery_broker_url=os.getenv("PYTIMETAG_CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"),
            celery_result_backend=os.getenv("PYTIMETAG_CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1"),
        )

    @property
    def storage_db_path(self) -> Path:
        return Path(self.storage_db).resolve()

    @property
    def datablock_dir_path(self) -> Path:
        return Path(self.datablock_dir).resolve()

