# dubbing — backend

FastAPI + SQLite service (SQLAlchemy 2.0 async + Alembic).

**The canonical documentation lives in [`../README.md`](../README.md).** Everything
below is the short version for when you are already inside `backend/`.

```bash
uv sync                      # install dependencies into backend/.venv
cp .env.example .env         # optional: override defaults
uv run alembic upgrade head  # create dubbing.db
uv run uvicorn app.main:app --reload     # start (Ctrl-C to stop)
```

Or via the Makefile (`make help` lists everything):

```bash
make install     # uv sync
make migrate     # alembic upgrade head
make dev         # foreground, autoreload
make start       # background (pidfile + uvicorn.log)
make stop        # stop the background server
make check       # lint + format check + tests
```
