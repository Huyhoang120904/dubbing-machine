"""Exception handlers that render every error as a `UnifiedResponse`.

Handlers are registered per app — FastAPI has no per-route handlers — so a failing
health probe answers with the envelope too. Only *successful* non-auth responses
stay bare.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import UnifiedResponse


def _envelope(status_code: int, message: str, data: Any = None) -> JSONResponse:
    body = UnifiedResponse[Any](status_code=status_code, message=message, data=data)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Covers our `HTTPException`s, 404 for an unknown path, and 405 for a wrong method."""
    return _envelope(exc.status_code, str(exc.detail))


def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """A 422 must still say which field failed, so the error list rides in `data`."""
    return _envelope(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Validation error",
        jsonable_encoder(exc.errors()),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire both handlers; called once from `create_app`."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
