from __future__ import annotations

import random
import threading
import time
from dataclasses import asdict, dataclass
from typing import Dict


@dataclass
class SessionState:
    running: bool = False
    source: str = "simulator"
    started_at: float = 0.0
    blocks: int = 0
    events_total: int = 0

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        if self.running and self.started_at > 0:
            payload["uptime_s"] = max(0.0, time.time() - self.started_at)
        else:
            payload["uptime_s"] = 0.0
        return payload


class RuntimeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.session = SessionState()
        self._ticker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start_session(self, source: str) -> SessionState:
        with self._lock:
            if self.session.running:
                return self.session
            self.session.running = True
            self.session.source = source
            self.session.started_at = time.time()
            self.session.blocks = 0
            self.session.events_total = 0
        self._stop_event.clear()
        self._ticker_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._ticker_thread.start()
        return self.session

    def stop_session(self) -> SessionState:
        with self._lock:
            self.session.running = False
        self._stop_event.set()
        return self.session

    def get_session(self) -> SessionState:
        with self._lock:
            return SessionState(
                running=self.session.running,
                source=self.session.source,
                started_at=self.session.started_at,
                blocks=self.session.blocks,
                events_total=self.session.events_total,
            )

    def _tick_loop(self) -> None:
        rng = random.Random(42)
        while not self._stop_event.is_set():
            time.sleep(1.0)
            with self._lock:
                if not self.session.running:
                    continue
                self.session.blocks += 1
                self.session.events_total += rng.randint(5_000, 20_000)

    def snapshot_metrics(self) -> Dict[str, object]:
        with self._lock:
            rate = 0 if not self.session.running else int(self.session.events_total / max(time.time() - self.session.started_at, 1))
            return {
                "running": self.session.running,
                "source": self.session.source,
                "blocks": self.session.blocks,
                "events_total": self.session.events_total,
                "events_rate_per_s": rate,
                "timestamp": time.time(),
            }

