.PHONY: dev dev-backend dev-frontend start start-backend start-frontend \
  restart restart-backend restart-frontend stop status

# ---------------------------------------------------------------------------
# Foreground dev (Ctrl+C kills both)
# ---------------------------------------------------------------------------
dev:
	@bash -c 'set -eo pipefail; \
	trap "kill 0" EXIT INT TERM; \
	python3 -m pytimetag gui --host 127.0.0.1 --port 8787 --reload --no-web & \
	cd webui && npm run dev & \
	wait'

dev-backend:
	python3 -m pytimetag gui --host 127.0.0.1 --port 8787 --reload --no-web

dev-frontend:
	cd webui && npm run dev

# ---------------------------------------------------------------------------
# Background start (detached, survives shell exit)
# ---------------------------------------------------------------------------
start: start-backend start-frontend

start-backend:
	@echo "Starting backend on 127.0.0.1:8787 ..."
	@nohup python3 -m pytimetag gui --host 127.0.0.1 --port 8787 --no-web \
	  > /tmp/pytimetag-backend.log 2>&1 &
	@echo "Backend PID: $$!"

start-frontend:
	@echo "Starting frontend dev server ..."
	@cd webui && nohup npm run dev \
	  > /tmp/pytimetag-frontend.log 2>&1 &
	@echo "Frontend PID: $$!"

# ---------------------------------------------------------------------------
# Stop / Kill
# ---------------------------------------------------------------------------
stop:
	@echo "Killing backend ..."
	@-pkill -f "python3.*pytimetag gui" 2>/dev/null && echo "  backend killed" || echo "  backend not running"
	@echo "Killing frontend ..."
	@-pkill -f "npm run dev" 2>/dev/null && echo "  frontend killed" || echo "  frontend not running"
	@-pkill -f "quasar dev" 2>/dev/null && echo "  quasar killed" || true

# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------
restart: stop start

restart-backend: stop start-backend

restart-frontend: stop start-frontend

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
status:
	@echo "=== Backend ==="
	@ps aux | grep -E "pytimetag gui" | grep -v grep || echo "  not running"
	@echo "=== Frontend ==="
	@ps aux | grep -E "npm run dev|quasar dev" | grep -v grep || echo "  not running"
	@echo "=== Ports ==="
	@lsof -i :8787 2>/dev/null || echo "  8787 free"
	@lsof -i :5173 2>/dev/null || echo "  5173 free"
