from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pytimetag.gui.celery_app import create_celery_app
from pytimetag.gui.config import GuiConfig
from pytimetag.gui.acquisition import AcquisitionService
from pytimetag.device.source_registry import list_cli_hardware_sources
from pytimetag.device.instance_manager import instance_manager
from pytimetag.device.datablock_packer import SplitByChannelEvent, SplitByTimeWindow


class OfflineProcessRequest(BaseModel):
    datablock_path: str


class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, Any]


class ConfigureAnalyserRequest(BaseModel):
    enabled: bool
    config: Optional[Dict[str, Any]] = None


class ChannelConfigRequest(BaseModel):
    dead_time_s: Optional[float] = None
    threshold_voltage: Optional[float] = None
    enabled: Optional[bool] = None
    mode: Optional[str] = None
    period_count: Optional[int] = None
    random_count: Optional[int] = None
    pulse_count: Optional[int] = None
    pulse_events: Optional[int] = None
    pulse_sigma_s: Optional[float] = None
    reference_pulse_v: Optional[float] = None


class WsHub:
    def __init__(self) -> None:
        self._clients: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._clients:
                self._clients.remove(websocket)

    async def broadcast_json(self, payload: Dict[str, Any]) -> None:
        dead: List[WebSocket] = []
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(json.dumps(payload, ensure_ascii=True))
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._clients:
                        self._clients.remove(ws)


def _init_gui_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS GUIJobs (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at DOUBLE NOT NULL,
            updated_at DOUBLE NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS GUISettings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at DOUBLE NOT NULL
        )
        """
    )


def _now() -> float:
    return time.time()


def create_app(config: GuiConfig) -> FastAPI:
    app = FastAPI(title="PyTimeTag GUI API", version="1.0.0")
    hub_metrics = WsHub()
    hub_logs = WsHub()

    stream_paths = config.resolved_stream_paths()
    for cfg in stream_paths:
        Path(cfg.datablock_dir).resolve().mkdir(parents=True, exist_ok=True)

    # Use the first path's DB for GUI metadata tables.
    gui_db_path = Path(stream_paths[0].storage_db).resolve()
    gui_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(gui_db_path))
    _init_gui_tables(conn)
    log_buffer: deque[Dict[str, Any]] = deque(maxlen=300)

    def append_log(level: str, message: str) -> None:
        log_buffer.append({"type": "log", "level": level, "message": message, "ts": _now()})

    celery = create_celery_app(config)

    # Determine split configuration.
    if config.split_mode == "time":
        window_ticks = int(round(config.split_s / 1e-12))
        if window_ticks <= 0:
            window_ticks = 1
        split_cfg: Any = SplitByTimeWindow(window_ticks)
    else:
        if config.split_channel < 0 or config.split_channel >= 16:
            raise ValueError("--split-channel must be in 0..15")
        split_cfg = SplitByChannelEvent(config.split_channel)

    resolution = 1e-12
    acquisition = AcquisitionService(
        stream_paths=stream_paths,
        channel_count=config.device_channel_count,
        resolution=resolution,
        split=split_cfg,
        metrics_cb=lambda m: None,
        log_cb=append_log,
        save_raw_data=config.save_raw_data,
    )

    # Create the single device instance via instance_manager.
    # Pass acquisition's word callback so the service receives the raw stream.
    if config.device_type == "simulator":
        try:
            instance_manager.create_simulator(
                serial_number=config.device_serial,
                channel_count=config.device_channel_count,
                data_callback=acquisition._on_words,
            )
        except ValueError:
            pass  # already exists
    else:
        raise ValueError(f"Unsupported GUI device type: {config.device_type}")

    device_instance = instance_manager.get_instance(config.device_type, config.device_serial)
    if device_instance is None:
        raise RuntimeError(f"Failed to initialize device {config.device_type}:{config.device_serial}")

    acquisition.start()
    instance_manager.start_instance(config.device_type, config.device_serial)
    append_log("info", "GUI API initialized")

    def read_settings() -> Dict[str, Any]:
        rows = conn.execute("SELECT key, value_json FROM GUISettings").fetchall()
        result: Dict[str, Any] = {}
        for key, value_json in rows:
            result[key] = json.loads(value_json)
        return result

    @app.get("/api/v1/meta")
    async def get_meta() -> Dict[str, Any]:
        return {
            "name": "pytimetag-gui",
            "api_version": "v1",
            "features": {
                "session_control": False,
                "offline_processing": True,
                "datablock_listing": True,
                "realtime_metrics_ws": True,
                "analyser_config": True,
                "settings": True,
            },
            "sources": ["simulator"] + list_cli_hardware_sources(),
        }

    @app.get("/api/v1/session/status")
    async def session_status() -> Dict[str, Any]:
        return acquisition.snapshot_metrics()

    @app.get("/api/v1/sources")
    async def list_sources() -> Dict[str, Any]:
        return {"items": ["simulator"] + list_cli_hardware_sources()}

    @app.get("/api/v1/device/current")
    async def get_current_device() -> Dict[str, Any]:
        inst = instance_manager.get_instance(config.device_type, config.device_serial)
        if inst is None:
            raise HTTPException(status_code=404, detail="No active device")
        return inst.to_dict()

    @app.get("/api/v1/stream_paths")
    async def get_stream_paths() -> Dict[str, Any]:
        return {
            "items": [
                {"name": cfg.name, "storage_db": cfg.storage_db, "datablock_dir": cfg.datablock_dir}
                for cfg in stream_paths
            ]
        }
        return inst.to_dict()

    @app.get("/api/v1/devices/{device_type}/{serial_number}/channels")
    async def get_device_channels(device_type: str, serial_number: str) -> Dict[str, Any]:
        """Get channel information for the active device instance."""
        try:
            channels = instance_manager.get_channel_info(config.device_type, config.device_serial)
            return {
                "device_type": config.device_type,
                "serial_number": config.device_serial,
                "channels": channels,
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/v1/devices/{device_type}/{serial_number}/channels/{channel_id}")
    async def set_device_channel(
        device_type: str,
        serial_number: str,
        channel_id: int,
        body: ChannelConfigRequest,
    ) -> Dict[str, Any]:
        """Set channel configuration for the active device instance."""
        try:
            cfg = body.dict(exclude_unset=True)
            instance_manager.set_channel_config(config.device_type, config.device_serial, channel_id, cfg)
            append_log("info", f"Channel {channel_id} updated for {config.device_type}:{config.device_serial}")
            return {
                "updated": True,
                "device_type": config.device_type,
                "serial_number": config.device_serial,
                "channel_id": channel_id,
                "config": cfg,
            }
        except ValueError as exc:
            detail = str(exc)
            status = 404 if "not found" in detail.lower() else 400
            raise HTTPException(status_code=status, detail=detail) from exc

    @app.get("/api/v1/analyzers")
    async def get_analyzers() -> Dict[str, Any]:
        return acquisition.analyser_status()

    @app.put("/api/v1/analyzers/{name}")
    async def configure_analyzer(name: str, body: ConfigureAnalyserRequest) -> Dict[str, Any]:
        try:
            data = acquisition.configure_analyser(name, body.enabled, body.config)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        append_log("info", f"Analyzer updated: {name}")
        await hub_logs.broadcast_json({"type": "log", "level": "info", "message": f"Analyzer updated: {name}"})
        return data

    @app.get("/api/v1/settings")
    async def get_settings() -> Dict[str, Any]:
        return {"settings": read_settings()}

    @app.put("/api/v1/settings")
    async def put_settings(body: SettingsUpdateRequest) -> Dict[str, Any]:
        now = _now()
        for key, value in body.settings.items():
            conn.execute(
                "INSERT OR REPLACE INTO GUISettings (key, value_json, updated_at) VALUES (?, ?, ?)",
                [key, json.dumps(value, ensure_ascii=True), now],
            )
        append_log("info", "Settings updated")
        await hub_logs.broadcast_json({"type": "log", "level": "info", "message": "Settings updated"})
        return {"settings": read_settings()}

    @app.get("/api/v1/datablocks")
    async def list_datablocks(limit: int = 100) -> Dict[str, Any]:
        # Aggregate datablocks across all paths.
        candidates: List[Path] = []
        for cfg in stream_paths:
            base = Path(cfg.datablock_dir).resolve()
            if base.exists():
                candidates.extend(base.rglob("*.datablock"))
        candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        return {
            "items": [
                {
                    "path": str(p),
                    "size": int(p.stat().st_size),
                    "mtime": float(p.stat().st_mtime),
                }
                for p in candidates
            ]
        }

    @app.post("/api/v1/offline/process")
    async def offline_process(body: OfflineProcessRequest) -> Dict[str, Any]:
        target = Path(body.datablock_path).resolve()
        if not target.exists():
            raise HTTPException(status_code=404, detail="DataBlock file not found")
        task = celery.send_task("pytimetag.gui.process_datablock", args=[str(target)])
        now = _now()
        conn.execute(
            "INSERT OR REPLACE INTO GUIJobs (id, kind, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            [task.id, "offline_process", "queued", now, now],
        )
        await hub_logs.broadcast_json({"type": "log", "level": "info", "message": f"Offline task queued: {task.id}"})
        append_log("info", f"Offline task queued: {task.id}")
        return {"job_id": task.id}

    @app.get("/api/v1/jobs/{job_id}")
    async def get_job(job_id: str) -> Dict[str, Any]:
        result = AsyncResult(job_id, app=celery)
        status = result.status.lower()
        now = _now()
        conn.execute("UPDATE GUIJobs SET status = ?, updated_at = ? WHERE id = ?", [status, now, job_id])
        payload: Dict[str, Any] = {"job_id": job_id, "status": status}
        if result.successful():
            payload["result"] = result.result
        elif result.failed():
            payload["error"] = str(result.result)
        return payload

    @app.get("/api/v1/jobs")
    async def list_jobs(limit: int = 50) -> Dict[str, Any]:
        rows = conn.execute(
            "SELECT id, kind, status, created_at, updated_at FROM GUIJobs ORDER BY updated_at DESC LIMIT ?",
            [int(limit)],
        ).fetchall()
        return {
            "items": [
                {
                    "id": r[0],
                    "kind": r[1],
                    "status": r[2],
                    "created_at": r[3],
                    "updated_at": r[4],
                }
                for r in rows
            ]
        }

    @app.websocket("/ws/metrics")
    async def ws_metrics(websocket: WebSocket) -> None:
        await hub_metrics.connect(websocket)
        try:
            while True:
                await websocket.send_json(acquisition.snapshot_metrics())
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            await hub_metrics.disconnect(websocket)

    @app.websocket("/ws/logs")
    async def ws_logs(websocket: WebSocket) -> None:
        await hub_logs.connect(websocket)
        try:
            for row in list(log_buffer):
                await websocket.send_json(row)
            while True:
                await asyncio.sleep(10.0)
        except WebSocketDisconnect:
            await hub_logs.disconnect(websocket)
        except BaseException:
            await hub_logs.disconnect(websocket)

    @app.get("/api/v1/logs")
    async def get_logs(limit: int = 200) -> Dict[str, Any]:
        rows = list(log_buffer)
        return {"items": rows[-int(limit):]}

    # Storage API - unified style: /storage/{collection}/{function}/{arg}
    @app.get("/api/v1/storage/collections")
    async def storage_list_collections(path: Optional[str] = None) -> Dict[str, Any]:
        storage = acquisition.get_storage(path)
        if storage.existCollections is None:
            await storage._Storage__senseExistCollections()
        return {"items": list(storage.existCollections) if storage.existCollections else []}

    @app.post("/api/v1/storage/{collection}/append")
    async def storage_append(collection: str, body: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
        storage = acquisition.get_storage(path)
        data = body.get("data", {})
        fetch_time = body.get("fetchTime")
        try:
            await storage.append(collection, data, fetch_time)
            return {"appended": True, "collection": collection}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/storage/{collection}/list")
    async def storage_list(
        collection: str,
        limit: int = 100,
        offset: int = 0,
        by: str = "FetchTime",
        after: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Dict[str, Any]:
        storage = acquisition.get_storage(path)
        try:
            items = await storage.latest(collection, by=by, after=after, length=limit + offset)
            if items is None:
                items = []
            elif not isinstance(items, list):
                items = [items]
            items = items[offset:]
            return {"items": items, "collection": collection, "limit": limit, "offset": offset}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/storage/{collection}/first")
    async def storage_first(
        collection: str,
        by: str = "FetchTime",
        after: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Dict[str, Any]:
        storage = acquisition.get_storage(path)
        try:
            result = await storage.first(collection, by=by, after=after, length=1)
            if result is None:
                raise HTTPException(status_code=404, detail="No items found")
            return result
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/storage/{collection}/range")
    async def storage_range(
        collection: str,
        begin: str,
        end: str,
        by: str = "FetchTime",
        limit: int = 1000,
        path: Optional[str] = None,
    ) -> Dict[str, Any]:
        storage = acquisition.get_storage(path)
        try:
            items = await storage.range(collection, begin=begin, end=end, by=by, limit=limit)
            return {"items": items, "collection": collection, "limit": limit}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/storage/{collection}/get/{value}")
    async def storage_get(
        collection: str,
        value: str,
        key: str = "_id",
        path: Optional[str] = None,
    ) -> Dict[str, Any]:
        storage = acquisition.get_storage(path)
        try:
            doc = await storage.get(collection, value, key=key)
            if doc is None:
                raise HTTPException(status_code=404, detail=f"Item with {key}='{value}' not found")
            return doc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete("/api/v1/storage/{collection}/delete/{value}")
    async def storage_delete(
        collection: str,
        value: str,
        key: str = "_id",
        path: Optional[str] = None,
    ) -> Dict[str, Any]:
        storage = acquisition.get_storage(path)
        try:
            await storage.delete(collection, value, key=key)
            await hub_logs.broadcast_json(
                {"type": "log", "level": "info", "message": f"Deleted {collection}/{value}"}
            )
            return {"deleted": True, "collection": collection, "key": key, "value": value}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.put("/api/v1/storage/{collection}/update/{id}")
    async def storage_update(collection: str, id: str, body: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
        storage = acquisition.get_storage(path)
        try:
            await storage.update(collection, id, body.get("value", {}))
            return {"updated": True, "collection": collection, "id": id}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    web_dist = Path(__file__).resolve().parent / "webui_dist"
    if config.serve_web and web_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(web_dist / "assets")), name="assets")

        @app.get("/")
        async def web_index() -> FileResponse:
            return FileResponse(web_dist / "index.html")

        @app.get("/{full_path:path}")
        async def web_fallback(full_path: str) -> FileResponse:
            _ = full_path
            return FileResponse(web_dist / "index.html")

    @app.get("/healthz")
    async def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> Dict[str, Any]:
        db_ok = True
        broker_ok = True
        try:
            conn.execute("SELECT 1").fetchone()
        except BaseException:
            db_ok = False
        try:
            with contextlib.closing(celery.connection_for_read()) as c:
                c.ensure_connection(max_retries=1)
        except BaseException:
            broker_ok = False
        return {"ready": db_ok and broker_ok, "duckdb": db_ok, "celery_broker": broker_ok}

    return app
