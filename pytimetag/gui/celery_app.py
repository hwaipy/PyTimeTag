from __future__ import annotations

from celery import Celery

from pytimetag.gui.config import GuiConfig


def create_celery_app(config: GuiConfig) -> Celery:
    app = Celery(
        "pytimetag_gui",
        broker=config.celery_broker_url,
        backend=config.celery_result_backend,
        include=["pytimetag.gui.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )
    return app

