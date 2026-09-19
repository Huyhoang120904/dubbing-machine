# Backend workspace. Every target runs with the working directory set here, so
# this file also works directly: `cd backend && make start`.
# From the repository root, the forwarding Makefile calls into this one.
.DEFAULT_GOAL := help

PY      := uv run
APP     := app.main:app
UVICORN := .venv/bin/uvicorn

HOST    ?= 127.0.0.1
PORT    ?= 8000
PIDFILE := .uvicorn.pid
LOGFILE := uvicorn.log
DBFILE  := dubbing.db

.PHONY: help install dev start stop restart status logs test test-cov lint fmt check \
        migrate revision downgrade history db-reset clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install/refresh dependencies from uv.lock (creates .venv)
	uv sync

dev: ## Run the API in the foreground with autoreload (Ctrl-C stops it)
	$(PY) uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

start: ## Start the API in the background (writes .uvicorn.pid and uvicorn.log)
	@test -x $(UVICORN) || { echo "No virtualenv found. Run 'make install' first."; exit 1; }
	@if [ -f $(PIDFILE) ] && kill -0 "$$(cat $(PIDFILE))" 2>/dev/null; then \
		echo "Already running (pid $$(cat $(PIDFILE))). Use 'make stop' or 'make restart'."; exit 1; \
	fi
	@nohup $(UVICORN) $(APP) --host $(HOST) --port $(PORT) >> $(LOGFILE) 2>&1 & echo $$! > $(PIDFILE)
	@sleep 1
	@if kill -0 "$$(cat $(PIDFILE))" 2>/dev/null; then \
		echo "Started on http://$(HOST):$(PORT) (pid $$(cat $(PIDFILE)); logs: $(LOGFILE))"; \
	else \
		echo "Failed to start — last lines of $(LOGFILE):"; tail -n 20 $(LOGFILE); rm -f $(PIDFILE); exit 1; \
	fi

stop: ## Stop the background server started with `make start`
	@if [ ! -f $(PIDFILE) ]; then \
		echo "Not running (no $(PIDFILE))."; \
		exit 0; \
	fi; \
	PID="$$(cat $(PIDFILE) 2>/dev/null)"; \
	case "$$PID" in \
		''|*[!0-9]*) echo "Corrupt pidfile — removing it."; rm -f $(PIDFILE); exit 0;; \
	esac; \
	if kill -0 "$$PID" 2>/dev/null; then \
		kill "$$PID"; \
		for _ in $$(seq 1 20); do kill -0 "$$PID" 2>/dev/null || break; sleep 0.5; done; \
		if kill -0 "$$PID" 2>/dev/null; then \
			echo "Still alive after 10s — sending SIGKILL to $$PID."; kill -9 "$$PID"; \
		else \
			echo "Stopped (pid $$PID)."; \
		fi; \
	else \
		echo "Stale pidfile (pid $$PID is not running)."; \
	fi; \
	rm -f $(PIDFILE)

restart: stop start ## Restart the background server

status: ## Report whether the server is running and healthy
	@if [ -f $(PIDFILE) ] && kill -0 "$$(cat $(PIDFILE))" 2>/dev/null; then \
		echo "process: running (pid $$(cat $(PIDFILE)))"; \
	else echo "process: not running"; fi
	@curl -fsS http://$(HOST):$(PORT)/health >/dev/null 2>&1 && echo "health:  ok ($(HOST):$(PORT)/health)" || echo "health:  unreachable"

logs: ## Follow the background server log
	@tail -f $(LOGFILE)

test: ## Run the test suite
	$(PY) pytest

test-cov: ## Run tests with a coverage report
	$(PY) pytest --cov --cov-report=term-missing

lint: ## Lint with ruff
	$(PY) ruff check .

fmt: ## Format with ruff
	$(PY) ruff format .

check: ## Lint + format check + tests (CI entrypoint)
	$(PY) ruff check .
	$(PY) ruff format --check .
	$(PY) pytest

migrate: ## Apply all migrations (alembic upgrade head)
	$(PY) alembic upgrade head

revision: ## Autogenerate a migration: make revision m="add foo"
	$(PY) alembic revision --autogenerate -m "$(m)"

downgrade: ## Roll back one migration: make downgrade (or make downgrade r=-2)
	$(PY) alembic downgrade $(or $(r),-1)

history: ## Show the migration history
	$(PY) alembic history --verbose

db-reset: ## Drop the local SQLite DB and re-migrate from scratch
	rm -f $(DBFILE) $(DBFILE)-shm $(DBFILE)-wal
	$(PY) alembic upgrade head

clean: ## Remove caches, build artifacts and runtime logs
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage build dist
	rm -f $(PIDFILE) $(LOGFILE)
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
