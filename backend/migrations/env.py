"""Alembic environment (async).

Key configuration choices:

* The database URL comes from `app.core.config.Settings`, not alembic.ini.
* `render_as_batch=True` — SQLite cannot `ALTER TABLE ... DROP CONSTRAINT` or
  most `ALTER COLUMN`, so Alembic must recreate tables instead. This is what
  makes `alembic revision --autogenerate` output usable on SQLite.
* `compare_type` / `compare_server_default` — catch column changes that the
  default comparison would silently miss.
* Models are imported so `Base.metadata` is complete before autogeneration.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

import app.db.models  # noqa: F401  # registers all models on Base.metadata
from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()

# `%` must be escaped for configparser interpolation.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

target_metadata = Base.metadata

# Options shared by the offline and online paths.
CONTEXT_OPTIONS: dict[str, object] = {
    "target_metadata": target_metadata,
    "compare_type": True,
    "compare_server_default": True,
    # Required for SQLite: emulate ALTER TABLE by recreating the table.
    "render_as_batch": True,
    "include_schemas": False,
}


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no DBAPI)."""
    context.configure(
        url=settings.database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **CONTEXT_OPTIONS,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on a synchronous connection supplied by the async engine."""
    context.configure(connection=connection, **CONTEXT_OPTIONS)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine, migrate through it, then dispose it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
