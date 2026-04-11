.PHONY: dev dev-backend dev-frontend

dev:
	@bash -c 'set -eo pipefail; \
	trap "kill 0" EXIT INT TERM; \
	python -m pytimetag gui --host 127.0.0.1 --port 8787 --reload --no-web & \
	cd webui && npm run dev & \
	wait'

dev-backend:
	python -m pytimetag gui --host 127.0.0.1 --port 8787 --reload --no-web

dev-frontend:
	cd webui && npm run dev
