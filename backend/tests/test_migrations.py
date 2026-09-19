"""Guard against ORM/migration drift.

These tests shell out to the real Alembic CLI against a temporary SQLite file, so
they also prove that `migrations/env.py` (async engine + batch mode) works.
`test_schema_matches_models` is the safety net: if someone adds a model column
without a migration, it fails here instead of in production.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(*args: str, database_url: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": database_url, "APP_ENV": "test", "SQL_ECHO": "false"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def migrated_db(tmp_path: Path) -> tuple[str, Path]:
    """Apply every migration to a fresh file-backed SQLite database."""
    db_path = tmp_path / "migrated.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"

    result = _run_alembic("upgrade", "head", database_url=database_url)
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stderr}"

    return database_url, db_path


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def test_upgrade_head_creates_expected_schema(migrated_db: tuple[str, Path]) -> None:
    _, db_path = migrated_db

    tables = _table_names(db_path)

    assert {"alembic_version", "users", "sessions"} <= tables


def test_items_table_is_gone(migrated_db: tuple[str, Path]) -> None:
    """The Item slice is deleted from both the models and the schema."""

    _, db_path = migrated_db

    assert "items" not in _table_names(db_path)


def test_users_table_has_a_unique_index_on_email(migrated_db: tuple[str, Path]) -> None:
    _, db_path = migrated_db

    with sqlite3.connect(db_path) as connection:
        indexes = {row[1]: row[2] for row in connection.execute("PRAGMA index_list('users')")}
        indexed_columns = {
            row[2] for row in connection.execute("PRAGMA index_info('ix_users_email')")
        }
        columns = {row[1] for row in connection.execute("PRAGMA table_info('users')")}

    assert indexes.get("ix_users_email") == 1, "ix_users_email must be a UNIQUE index"
    assert indexed_columns == {"email"}
    assert columns == {"id", "email", "hashed_password", "created_at", "updated_at"}


def test_sessions_table_has_a_unique_token_digest_and_cascades_from_users(
    migrated_db: tuple[str, Path],
) -> None:
    _, db_path = migrated_db

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info('sessions')")}
        indexes = {row[1]: row[2] for row in connection.execute("PRAGMA index_list('sessions')")}
        # PRAGMA foreign_key_list -> (id, seq, table, from, to, on_update, on_delete, match)
        foreign_keys = {
            (row[2], row[3], row[4], row[6])
            for row in connection.execute("PRAGMA foreign_key_list('sessions')")
        }

    assert columns == {
        "id",
        "user_id",
        "token_hash",
        "expires_at",
        "revoked_at",
        "created_at",
        "updated_at",
    }
    assert indexes.get("ix_sessions_token_hash") == 1, "ix_sessions_token_hash must be UNIQUE"
    assert "ix_sessions_user_id" in indexes
    assert foreign_keys == {("users", "user_id", "id", "CASCADE")}


def test_downgrade_base_is_reversible(migrated_db: tuple[str, Path]) -> None:
    database_url, db_path = migrated_db

    result = _run_alembic("downgrade", "base", database_url=database_url)

    assert result.returncode == 0, f"alembic downgrade base failed:\n{result.stderr}"
    assert not {"items", "users", "sessions"} & _table_names(db_path)


def test_schema_matches_models(migrated_db: tuple[str, Path]) -> None:
    """Every ORM model must exist in the migrated schema."""
    from app.db.base import Base

    _, db_path = migrated_db

    missing = set(Base.metadata.tables) - _table_names(db_path)

    assert not missing, f"models missing a migration: {sorted(missing)}"


def test_migrations_are_in_sync_with_models(migrated_db: tuple[str, Path]) -> None:
    """`alembic check` fails when autogenerate would detect pending changes.

    This is the guard for "I added a column to a model but forgot the migration".
    """
    database_url, _ = migrated_db

    result = _run_alembic("check", database_url=database_url)

    assert result.returncode == 0, (
        "Models and migrations have diverged (or `alembic check` errored).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
