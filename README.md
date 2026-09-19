# dubbing

FastAPI + SQLite service. Async SQLAlchemy 2.0, Alembic migrations, Pydantic v2, `uv`.

All application code lives in [`backend/`](backend/). `README.md` (this file) and
`.gitignore` stay at the repository root; everything else is under `backend/`.

```
.
├── Makefile              # forwards every target to backend/ (make start, make test, ...)
├── README.md             # you are here
├── .gitignore
└── backend/
    ├── Makefile          # the real targets, runnable from here or via the root Makefile
    ├── pyproject.toml    # dependencies, ruff and pytest config
    ├── uv.lock           # locked dependency graph (commit this)
    ├── alembic.ini
    ├── .env.example
    ├── app/              # application package
    ├── migrations/       # Alembic environment + versions/
    ├── tests/
    ├── .venv/            # created by `make install` (git-ignored)
    ├── dubbing.db        # created by `make migrate` (git-ignored)
    └── uvicorn.log       # created by `make start` (git-ignored)
```

> Every `make` target works from the repository root *or* from `backend/`. The
> commands below use the root; `cd backend` first if you prefer.

## Prerequisites

| Requirement | Notes |
| --- | --- |
| **Python 3.11+** | `requires-python = ">=3.11"`. `uv` can install it for you. |
| **[uv](https://docs.astral.sh/uv/)** | Dependency manager used by this project. |
| `curl` | Only used by `make status` to probe `/health`. |

Install `uv` (and Python 3.11 if your system one is older):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # or: pipx install uv
uv python install 3.11
```

## Install dependencies

```bash
git clone <your-repo-url> dubbing
cd dubbing
make install          # == cd backend && uv sync
```

`make install` creates `backend/.venv` and installs the exact versions pinned in
`backend/uv.lock`. Re-run it after pulling changes to `pyproject.toml` or
`uv.lock`. Add a dependency with:

```bash
cd backend && uv add httpx          # runtime dependency
cd backend && uv add --dev pytest   # dev-only dependency
```

Then create the database (fresh checkout only, and whenever new migrations land):

```bash
cp backend/.env.example backend/.env    # optional; sensible defaults are built in
make migrate                            # == alembic upgrade head
```

`make help` lists every available target.

## Start

**Development — foreground with auto-reload.** Logs stream to your terminal:

```bash
make dev                # http://127.0.0.1:8000
make dev PORT=9000      # a different port
```

Stop it with **Ctrl-C**.

**Background — detached, for leaving it running:**

```bash
make start              # writes backend/.uvicorn.pid and backend/uvicorn.log
make start PORT=9000
```

`make start` prints the PID and refuses to start a second instance if one is
already running (it does *not* use `--reload`).

Either way, once it is up:

* API docs (Swagger UI): <http://127.0.0.1:8000/docs>
* Health probe: <http://127.0.0.1:8000/health>

> Run against a migrated database (`make migrate`), otherwise `/api/v1/health/db` and
> the `/api/v1/auth/*` endpoints fail with "no such table: users".

## Stop

| How it was started | How to stop it |
| --- | --- |
| `make dev` (foreground) | **Ctrl-C** |
| `make start` (background) | `make stop` |

```bash
make stop        # SIGTERM, waits up to 10s, then SIGKILL; clears the pidfile
make restart     # stop + start
make status      # is the process running, and is /health reachable?
make logs        # tail -f backend/uvicorn.log
```

If a crash leaves a stale pidfile, `make stop` notices the dead PID, reports
"Stale pidfile" and cleans up — so it is always safe to run. To kill the server
by hand: `pkill -f 'app.main:app'`.

## Migrations

```bash
make migrate                  # apply everything (alembic upgrade head)
make revision m="add tags"    # autogenerate a migration from model changes
make downgrade                # roll back one revision
make downgrade r=-2           # roll back two
make history                  # show the revision chain
make db-reset                 # delete dubbing.db and re-migrate from scratch
```

After changing a model in `backend/app/db/models/`, always run
`make revision m="..."` and **read the generated file** before committing.
`make check` verifies models and migrations are in sync (via `alembic check` in
`tests/test_migrations.py`), so a model change without a migration fails CI.

## Tests, lint, format

```bash
make test         # pytest
make test-cov     # pytest with coverage
make lint         # ruff check
make fmt          # ruff format
make check        # lint + format check + tests — the CI entrypoint
make clean        # drop caches, logs and build artifacts
```

## Configuration

Settings live in `backend/app/core/config.py` and are read from the environment;
`backend/.env` is loaded too, but real environment variables win. Copy
`backend/.env.example` to `backend/.env` to override anything:

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_NAME` | `dubbing` | Shown in docs and logs. |
| `APP_ENV` | `local` | `local` / `test` / `staging` / `production`. |
| `DEBUG` | `false` | FastAPI debug mode. |
| `API_V1_PREFIX` | `/api/v1` | Mount point of the versioned router. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./dubbing.db` | Must use an async driver; relative paths resolve against `backend/`. |
| `SQL_ECHO` | `false` | Log every SQL statement. |
| `CORS_ORIGINS` | `[]` | JSON array, e.g. `["http://localhost:3000"]`. |
| `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`. |
| `JWT_SECRET_KEY` | `change-me-in-production` | Startup fails if the default is still set while `APP_ENV` is `staging`/`production`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access-token lifetime. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh-session lifetime. |

A sync `DATABASE_URL` (e.g. `sqlite:///...`) is rejected at startup on purpose —
the engine is async.

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Service metadata |
| GET | `/health` | Unversioned liveness probe |
| GET | `/api/v1/health` | Versioned liveness |
| GET | `/api/v1/health/db` | Readiness (database round-trip) |
| POST | `/api/v1/auth/register` | Create an account (`409` on duplicate email) |
| POST | `/api/v1/auth/login` | Exchange email + password for an access/refresh token pair |
| POST | `/api/v1/auth/refresh` | Rotate a refresh token (the old one stops working) |
| POST | `/api/v1/auth/logout` | Revoke a refresh token (`200` with `data: null`) |
| GET | `/api/v1/auth/me` | The authenticated user |

```bash
# Register, then log in
curl -X POST localhost:8000/api/v1/auth/register \
  -H 'content-type: application/json' \
  -d '{"email":"you@example.com","password":"supersecret"}'

curl -X POST localhost:8000/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"you@example.com","password":"supersecret"}'
# -> {"status_code":200,"message":"Login successful","data":{"access_token":"...",
#     "refresh_token":"...","token_type":"bearer","expires_in":900,"refresh_expires_in":2592000}}

curl localhost:8000/api/v1/auth/me -H 'Authorization: Bearer <access_token>'

# Errors look the same
# -> {"status_code":401,"message":"Invalid email or password","data":null}
```

Request flow: `routes → services → repositories → session`. Routes hold no SQL and no
business rules; `AuthService` raises `EmailAlreadyRegisteredError` /
`InvalidCredentialsError` / `InvalidSessionError`, which routes translate into
`409` / `401`. Repositories `flush()`, the service `commit()`s.

The auth routes answer with a response envelope (`status_code`, `message`, `data`), and
error responses use it everywhere. `/`, `/health`, `/api/v1/health` and
`/api/v1/health/db` stay bare for probes.

## Doing it without make

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload              # foreground
nohup .venv/bin/uvicorn app.main:app &            # background
pgrep -af 'app.main:app'                          # find it
pkill -f 'app.main:app'                           # stop it
uv run pytest
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `no such table: users` | Database not migrated: `make migrate` (or `make db-reset`). |
| `401` on every authenticated call | The access token lives 15 minutes: `POST /api/v1/auth/refresh`. If refresh also fails, `JWT_SECRET_KEY` changed since the token was issued — log in again. |
| `No virtualenv found. Run 'make install' first.` | Run `make install`. |
| `Address already in use` | Something holds the port: `make status`, then `make stop` (or `make dev PORT=8001`). |
| `database is locked` | A leftover process holds a write lock: `pkill -f 'app.main:app'`. WAL mode and a 5s `busy_timeout` are already configured. |
| `make stop` reports "Stale pidfile" | Harmless — a previous run died without cleanup; the pidfile is removed for you. |
| Changes to `.env` seem ignored | It is read at startup: `make restart`. |
| `ruff`/`pytest` not found | Dependencies live in `backend/.venv`; run them via `uv run` (or `make`) instead of a global install. |