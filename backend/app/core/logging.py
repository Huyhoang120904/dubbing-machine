"""Logging setup built on the standard library."""

from __future__ import annotations

import logging
from logging.config import dictConfig

from app.core.config import Settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(settings: Settings) -> None:
    """Apply a dictConfig-based logging setup. Idempotent and safe to call twice."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"format": LOG_FORMAT, "datefmt": "%Y-%m-%dT%H:%M:%S%z"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"handlers": ["console"], "level": settings.log_level},
            "loggers": {
                # Uvicorn installs its own handlers; reuse ours for consistency.
                "uvicorn": {
                    "handlers": ["console"],
                    "level": settings.log_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": settings.log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": settings.log_level,
                    "propagate": False,
                },
                # SQLAlchemy echoes SQL through this logger; quiet unless debugging.
                "sqlalchemy.engine": {
                    "handlers": ["console"],
                    "level": "INFO" if settings.sql_echo else "WARNING",
                    "propagate": False,
                },
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Thin wrapper so call sites do not import `logging` directly."""
    return logging.getLogger(name)
