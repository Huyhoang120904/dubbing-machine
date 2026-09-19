"""ORM models.

Every model module must be imported here so that `Base.metadata` is fully
populated before Alembic autogenerate runs.
"""

from app.db.models.item import Item

__all__ = ["Item"]
