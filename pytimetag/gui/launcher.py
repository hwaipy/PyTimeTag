from __future__ import annotations

import os

import uvicorn

from pytimetag.gui.api import create_app
from pytimetag.gui.config import GuiConfig


def _create_app_from_env():
    return create_app(GuiConfig.from_env())


def run_gui_server(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
    serve_web: bool | None = None,
) -> None:
    config = GuiConfig.from_env()
    if host is not None:
        config = GuiConfig(
            host=host,
            port=config.port,
            storage_db=config.storage_db,
            datablock_dir=config.datablock_dir,
            celery_broker_url=config.celery_broker_url,
            celery_result_backend=config.celery_result_backend,
            serve_web=config.serve_web,
        )
    if port is not None:
        config = GuiConfig(
            host=config.host,
            port=port,
            storage_db=config.storage_db,
            datablock_dir=config.datablock_dir,
            celery_broker_url=config.celery_broker_url,
            celery_result_backend=config.celery_result_backend,
            serve_web=config.serve_web,
        )
    if serve_web is not None:
        config = GuiConfig(
            host=config.host,
            port=config.port,
            storage_db=config.storage_db,
            datablock_dir=config.datablock_dir,
            celery_broker_url=config.celery_broker_url,
            celery_result_backend=config.celery_result_backend,
            serve_web=serve_web,
        )
    if reload:
        # Uvicorn reloader requires an import string or app factory.
        os.environ["PYTIMETAG_GUI_SERVE_WEB"] = "1" if config.serve_web else "0"
        uvicorn.run(
            "pytimetag.gui.launcher:_create_app_from_env",
            host=config.host,
            port=config.port,
            log_level="info",
            reload=True,
            factory=True,
        )
        return
    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info", reload=False)

