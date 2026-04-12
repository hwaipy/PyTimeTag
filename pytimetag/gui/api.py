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


class StartSessionRequest(BaseModel):
    source: str = "simulator"


class OfflineProcessRequest(BaseModel):
    datablock_path: str


class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, Any]


class ConfigureAnalyserRequest(BaseModel):
    enabled: bool
    config: Optional[Dict[str, Any]] = None


class StorageQueryRequest(BaseModel):
    limit: int = 100
    offset: int = 0
    order_by: str = "FetchTime"
    order_desc: bool = True
    after: Optional[str] = None
    filter: Optional[Dict[str, Any]] = None


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

    config.storage_db_path.parent.mkdir(parents=True, exist_ok=True)
    config.datablock_dir_path.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(config.storage_db_path))
    _init_gui_tables(conn)
    log_buffer: deque[Dict[str, Any]] = deque(maxlen=300)

    def append_log(level: str, message: str) -> None:
        log_buffer.append({"type": "log", "level": level, "message": message, "ts": _now()})

    celery = create_celery_app(config)
    acquisition = AcquisitionService(
        storage_db=config.storage_db_path,
        datablock_dir=config.datablock_dir_path,
        metrics_cb=lambda m: None,
        log_cb=append_log,
    )
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
                "session_control": True,
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

    @app.post("/api/v1/session/start")
    async def session_start(body: StartSessionRequest) -> Dict[str, Any]:
        if body.source != "simulator":
            raise HTTPException(status_code=400, detail="Current GUI build supports simulator source only.")
        acquisition.start(body.source)
        await hub_logs.broadcast_json({"type": "log", "level": "info", "message": f"Session started ({body.source})"})
        return acquisition.snapshot_metrics()

    @app.post("/api/v1/session/stop")
    async def session_stop() -> Dict[str, Any]:
        acquisition.stop()
        await hub_logs.broadcast_json({"type": "log", "level": "info", "message": "Session stopped"})
        return acquisition.snapshot_metrics()

    @app.get("/api/v1/sources")
    async def list_sources() -> Dict[str, Any]:
        return {"items": ["simulator"] + list_cli_hardware_sources()}

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
        base = config.datablock_dir_path
        candidates = sorted(base.rglob("*.datablock"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
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

    @app.get("/api/v1/storage/collections")
    async def list_storage_collections() -> Dict[str, Any]:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema() AND table_name LIKE 'Storage_%'"
        ).fetchall()
        collections = [r[0][8:] for r in rows]
        return {"items": collections}

    @app.get("/api/v1/storage/{collection}")
    async def query_storage_collection(
        collection: str,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "FetchTime",
        order_desc: bool = True,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        from pytimetag.storage import Storage

        storage = Storage(conn, timezone="utc")
        try:
            await storage._Storage__senseExistCollections()
            if collection not in storage.existCollections:
                raise HTTPException(status_code=404, detail=f"Collection '{collection}' not found")
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        try:
            items = await storage.latest(
                collection,
                by=order_by,
                after=after,
                length=limit + offset,
            )
            if items is None:
                items = []
            elif not isinstance(items, list):
                items = [items]
            items = items[offset:]
            return {"items": items, "collection": collection, "limit": limit, "offset": offset}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/storage/{collection}/{item_id}")
    async def get_storage_item(collection: str, item_id: str) -> Dict[str, Any]:
        from pytimetag.storage import Storage

        storage = Storage(conn, timezone="utc")
        try:
            doc = await storage.get(collection, item_id, key="_id")
            if doc is None:
                raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found in collection '{collection}'")
            return doc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete("/api/v1/storage/{collection}/{item_id}")
    async def delete_storage_item(collection: str, item_id: str) -> Dict[str, Any]:
        # Use acquisition service's storage connection
        storage = acquisition._storage
        try:
            await storage.delete(collection, item_id, key="_id")
            await hub_logs.broadcast_json(
                {"type": "log", "level": "info", "message": f"Deleted {collection}/{item_id}"}
            )
            return {"deleted": True, "collection": collection, "id": item_id}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

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

