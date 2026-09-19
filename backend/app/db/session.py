"""Async engine, session factory and the `get_db` dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

settings = get_settings()


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Enforce SQLite best practices on every new DBAPI connection.

    `foreign_keys` is OFF by default in SQLite, and WAL gives us readers that do
    not block the writer.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def build_engine(url: str | None = None, *, echo: bool | None = None) -> AsyncEngine:
    """Create an `AsyncEngine` for `url` (defaults to the configured URL).

    Kept as a function so tests can spin up isolated engines (in-memory or on a
    temporary file) without touching global state.
    """
    database_url = url or settings.database_url
    engine_kwargs: dict[str, object] = {
        "echo": settings.sql_echo if echo is None else echo,
        "future": True,
    }

    if database_url.startswith("sqlite"):
        in_memory = ":memory:" in database_url
        if in_memory:
            # A single shared connection keeps the in-memory schema visible to
            # every session in the test suite.
            engine_kwargs["poolclass"] = StaticPool
        else:
            engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["connect_args"] = {"timeout": 30, "check_same_thread": False}
        engine = create_async_engine(database_url, **engine_kwargs)
        event.listen(engine.sync_engine, "connect", _configure_sqlite_connection)
        return engine

    engine_kwargs["pool_pre_ping"] = True
    return create_async_engine(database_url, **engine_kwargs)


engine: AsyncEngine = build_engine()

# `expire_on_commit=False` so response serialization does not trigger lazy I/O
# after the commit; `autoflush=False` avoids surprise flushes mid-transaction.
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped session.

    The session is always closed; on error the transaction is rolled back
    explicitly so nothing half-applied leaks into the pool.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
