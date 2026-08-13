"""Standard error responses: every error is {"error": {code, message, details?}}."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
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
    """Domain-level validation failed (semantically invalid input).

    ``details`` is deliberately untyped past ``list``. It began as a list
    of sentences, which is all a paste-a-YAML form can use; a form with
    thirty fields needs to know *which* field each sentence is about, and
    that is a mapping rather than a sentence. Both shapes travel in the
    same list and both serialise, so widening it costs no caller a change
    (see :func:`field_errors`).
    """

    def __init__(self, message: str, details: list[Any] | None = None) -> None:
        self.details = details or []
        super().__init__(message)


def field_errors(error: Exception) -> list[dict[str, str]]:
    """Pydantic's own complaints, each tagged with the field it is about.

    **This copies no rule.** The server still decides what is valid; all
    this does is keep the *address* pydantic already computed instead of
    flattening it into prose. Without it a form can only print one blob
    and leave the reader to work out that "goal_tolerance_rad = 0.35
    constrains the arrival heading" refers to a field thirty rows down.

    ``loc`` is joined with dots, so a nested failure reads
    ``missions.0.start`` — the same path the profile YAML uses, which is
    what makes it usable by both the form and the paste box.

    Duck-typed rather than importing pydantic: the callers catch
    ``Exception`` on purpose ("ValidationError and friends"), and an
    error that turns out not to carry field locations should degrade to
    an empty list rather than raise while reporting an error.
    """
    collect = getattr(error, "errors", None)
    if not callable(collect):
        return []
    try:
        raw = collect()
    except Exception:  # noqa: BLE001 - never fail while reporting a failure
        return []
    entries: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        location = item.get("loc") or ()
        entries.append(
            {
                # Empty for a whole-model failure, which is honest: the
                # complaint is about the profile, not about one field.
                "path": ".".join(str(part) for part in location),
                "message": str(item.get("msg", "")),
            }
        )
    return entries


class InvalidStateError(Exception):
    """Operation not allowed in the resource's current state."""


def _safe_details(errors: Any) -> Any:
    """Make a validation error safe to serialise, whatever is inside it.

    Pydantic puts arbitrary Python objects into an error's ``ctx`` and
    ``input``, and FastAPI's own encoder raises on some of them. A file
    upload is the case that bites: a required ``File()`` parameter carries
    the literal ``...`` as its default, and ``jsonable_encoder`` dies on
    it with ``'ellipsis' object is not iterable``.

    The handler then raises *while reporting an error*, so the 500 handler
    takes over and a plain missing-field mistake reaches the client as an
    opaque internal error. Anything not natively JSON is stringified here
    instead — a slightly less precise message beats an unusable one.
    """
    if isinstance(errors, dict):
        return {str(key): _safe_details(value) for key, value in errors.items()}
    if isinstance(errors, (list, tuple)):
        return [_safe_details(item) for item in errors]
    if errors is None or isinstance(errors, (str, bool, int, float)):
        return errors
    return str(errors)


def _error_body(code: str, message: str, details: Any = None) -> dict:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register_error_handlers(app: FastAPI) -> None:
    # Imported here to keep this module free of auth/domain imports at
    # module scope (errors.py is imported very early).
    from planbench_agent.provider import ProviderError, ProviderUnavailable
    from planbench_api.accounts import AccountError
    from planbench_api.approval import PermissionDenied, TransitionError
    from planbench_api.auth import AuthError, Forbidden
    from planbench_api.model_registry import ModelNotAllowed, RegistryError
    from planbench_api.oauth import OAuthError
    from planbench_api.review import ReviewError, ReviewNotAllowed
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

    # Before ReviewError, which it subclasses: being the wrong person is a
    # 403, while asking for something impossible is a 422.
    @app.exception_handler(ReviewNotAllowed)
    async def review_not_allowed(_: Request, exc: ReviewNotAllowed) -> JSONResponse:
        return JSONResponse(status_code=403, content=_error_body("forbidden", str(exc)))

    @app.exception_handler(ReviewError)
    async def review_invalid(_: Request, exc: ReviewError) -> JSONResponse:
        return JSONResponse(status_code=422, content=_error_body("validation_error", str(exc)))

    @app.exception_handler(AccountError)
    async def bad_account_request(_: Request, exc: AccountError) -> JSONResponse:
        return JSONResponse(status_code=422, content=_error_body("validation_error", str(exc)))

    # Before RegistryError, which it subclasses: being the wrong person
    # is a 403, asking for something impossible is a 422.
    @app.exception_handler(ModelNotAllowed)
    async def model_not_allowed(_: Request, exc: ModelNotAllowed) -> JSONResponse:
        return JSONResponse(status_code=403, content=_error_body("forbidden", str(exc)))

    @app.exception_handler(RegistryError)
    async def registry_invalid(_: Request, exc: RegistryError) -> JSONResponse:
        # Every message here is written for the person uploading, not
        # for a log: "this is not a zip archive" rather than a traceback.
        return JSONResponse(status_code=422, content=_error_body("validation_error", str(exc)))

    @app.exception_handler(OAuthError)
    async def oauth_failed(_: Request, exc: OAuthError) -> JSONResponse:
        # The message is written for the person who has to fix it and
        # never contains a token, a code or a client secret.
        logger.warning("oauth failure: %s", exc)
        return JSONResponse(status_code=400, content=_error_body("oauth_error", str(exc)))

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
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "request_validation_error", "invalid request", _safe_details(exc.errors())
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Never leak stack traces to clients; log them server-side.
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500, content=_error_body("internal_error", "internal server error")
        )
