from __future__ import annotations

import os
from typing import List, Optional

import uvicorn

from pytimetag.gui.api import create_app
from pytimetag.gui.config import GuiConfig, StreamPathConfig


def _create_app_from_env():
    return create_app(GuiConfig.from_env())


def _set_env_from_config(config: GuiConfig) -> None:
    os.environ["PYTIMETAG_GUI_HOST"] = config.host
    os.environ["PYTIMETAG_GUI_PORT"] = str(config.port)
    os.environ["PYTIMETAG_STORAGE_DB"] = config.storage_db
    os.environ["PYTIMETAG_DATABLOCK_DIR"] = config.datablock_dir
    os.environ["PYTIMETAG_CELERY_BROKER_URL"] = config.celery_broker_url
    os.environ["PYTIMETAG_CELERY_RESULT_BACKEND"] = config.celery_result_backend
    os.environ["PYTIMETAG_GUI_SERVE_WEB"] = "1" if config.serve_web else "0"
    os.environ["PYTIMETAG_SAVE_RAW_DATA"] = "1" if config.save_raw_data else "0"
    os.environ["PYTIMETAG_DEVICE_TYPE"] = config.device_type
    os.environ["PYTIMETAG_DEVICE_SERIAL"] = config.device_serial
    os.environ["PYTIMETAG_DEVICE_CHANNEL_COUNT"] = str(config.device_channel_count)
    os.environ["PYTIMETAG_SPLIT_MODE"] = config.split_mode
    os.environ["PYTIMETAG_SPLIT_S"] = str(config.split_s)
    os.environ["PYTIMETAG_SPLIT_CHANNEL"] = str(config.split_channel)
    if config.stream_paths:
        paths_str = ";".join(
            f"{p.name}:{p.storage_db}:{p.datablock_dir}" for p in config.stream_paths
        )
        os.environ["PYTIMETAG_STREAM_PATHS"] = paths_str
    elif "PYTIMETAG_STREAM_PATHS" in os.environ:
        del os.environ["PYTIMETAG_STREAM_PATHS"]


def run_gui_server(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
    serve_web: bool | None = None,
    stream_paths: Optional[List[StreamPathConfig]] = None,
) -> None:
    config = GuiConfig.from_env()
    kwargs = {
        "host": config.host,
        "port": config.port,
        "storage_db": config.storage_db,
        "datablock_dir": config.datablock_dir,
        "celery_broker_url": config.celery_broker_url,
        "celery_result_backend": config.celery_result_backend,
        "serve_web": config.serve_web,
        "save_raw_data": config.save_raw_data,
        "stream_paths": config.stream_paths,
        "device_type": config.device_type,
        "device_serial": config.device_serial,
        "device_channel_count": config.device_channel_count,
        "split_mode": config.split_mode,
        "split_s": config.split_s,
        "split_channel": config.split_channel,
    }
    if host is not None:
        kwargs["host"] = host
    if port is not None:
        kwargs["port"] = port
    if serve_web is not None:
        kwargs["serve_web"] = serve_web
    if stream_paths is not None:
        kwargs["stream_paths"] = stream_paths
    config = GuiConfig(**kwargs)
    if reload:
        _set_env_from_config(config)
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
