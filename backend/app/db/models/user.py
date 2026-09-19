"""`User` model — an account that can log in."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 320 is the maximum length of an email address; stored stripped and lowercased.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<User id={self.id} email={self.email!r}>"
