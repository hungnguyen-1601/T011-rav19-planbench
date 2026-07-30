"""Standard error responses: every error is {"error": {code, message, details?}}."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("planbench.api")


class NotFoundError(Exception):
    """A referenced resource does not exist."""

    def __init__(self, resource: str, key: str) -> None:
        self.resource = resource
        self.key = key
        super().__init__(f"{resource} {key!r} not found")


class DomainValidationError(Exception):
    """Domain-level validation failed (semantically invalid input)."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        self.details = details or []
        super().__init__(message)


class InvalidStateError(Exception):
    """Operation not allowed in the resource's current state."""


def _error_body(code: str, message: str, details: Any = None) -> dict:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register_error_handlers(app: FastAPI) -> None:
    # Imported here to keep this module free of auth/domain imports at
    # module scope (errors.py is imported very early).
    from planbench_agent.provider import ProviderError, ProviderUnavailable
    from planbench_api.approval import PermissionDenied, TransitionError
    from planbench_api.auth import AuthError, Forbidden
    from planbench_benchmark.registry import AlgorithmConfigError, UnknownAlgorithmError

    # Registered before ProviderError because it is a subclass; FastAPI
    # picks the handler for the most specific registered type, and a
    # missing key deserves a different status and a different fix than a
    # provider that answered badly.
    @app.exception_handler(ProviderUnavailable)
    async def provider_unavailable(_: Request, exc: ProviderUnavailable) -> JSONResponse:
        logger.warning("agent provider unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content=_error_body("provider_unavailable", str(exc)),
        )

    @app.exception_handler(ProviderError)
    async def provider_failed(_: Request, exc: ProviderError) -> JSONResponse:
        # 502: PlanBench is fine, the upstream model is not. Returning
        # the provider's own message matters — "Function call is missing
        # a thought_signature" is actionable, "internal server error" is
        # not.
        logger.warning("agent provider error: %s", exc)
        return JSONResponse(status_code=502, content=_error_body("provider_error", str(exc)))

    @app.exception_handler(AuthError)
    async def auth_failed(_: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_error_body("unauthenticated", str(exc)),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(Forbidden)
    async def forbidden(_: Request, exc: Forbidden) -> JSONResponse:
        return JSONResponse(status_code=403, content=_error_body("forbidden", str(exc)))

    @app.exception_handler(PermissionDenied)
    async def permission_denied(_: Request, exc: PermissionDenied) -> JSONResponse:
        return JSONResponse(status_code=403, content=_error_body("forbidden", str(exc)))

    @app.exception_handler(TransitionError)
    async def bad_transition(_: Request, exc: TransitionError) -> JSONResponse:
        return JSONResponse(status_code=409, content=_error_body("invalid_state", str(exc)))

    @app.exception_handler(UnknownAlgorithmError)
    async def unknown_algorithm(_: Request, exc: UnknownAlgorithmError) -> JSONResponse:
        return JSONResponse(status_code=422, content=_error_body("validation_error", str(exc)))

    @app.exception_handler(AlgorithmConfigError)
    async def bad_algorithm_config(_: Request, exc: AlgorithmConfigError) -> JSONResponse:
        return JSONResponse(status_code=422, content=_error_body("validation_error", str(exc)))

    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=_error_body("not_found", str(exc)))

    @app.exception_handler(DomainValidationError)
    async def domain_invalid(_: Request, exc: DomainValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body("validation_error", str(exc), exc.details),
        )

    @app.exception_handler(InvalidStateError)
    async def invalid_state(_: Request, exc: InvalidStateError) -> JSONResponse:
        return JSONResponse(status_code=409, content=_error_body("invalid_state", str(exc)))

    @app.exception_handler(RequestValidationError)
    async def request_invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        # errors() can contain raw exception objects in ctx -> encode safely.
        details = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
        return JSONResponse(
            status_code=422,
            content=_error_body("request_validation_error", "invalid request", details),
        )

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Never leak stack traces to clients; log them server-side.
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500, content=_error_body("internal_error", "internal server error")
        )
