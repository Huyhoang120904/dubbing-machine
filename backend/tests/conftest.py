"""Shared pytest fixtures.

Tests run against a throwaway in-memory SQLite database whose schema is created
straight from the ORM metadata (fast), while `test_migrations.py` separately
verifies that the Alembic migration chain produces the same schema.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.db.base import Base
from app.db.session import build_engine, get_db
from app.main import create_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Isolated in-memory engine with the full schema applied."""
    test_engine = build_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield test_engine
    finally:
        await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A session for tests that need to seed or assert data directly."""
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    """HTTP client wired to the app with `get_db` pointed at the test database."""
    app = create_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()
