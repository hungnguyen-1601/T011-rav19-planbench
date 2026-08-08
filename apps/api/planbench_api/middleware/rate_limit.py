"""Rate limiting middleware to prevent brute force and denial of service attacks."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Simple sliding window rate limiter per client IP and path prefix."""

    def __init__(
        self,
        app: Callable,
        max_requests: int = 5,
        window_seconds: int = 60,
        path_prefix: str = "/auth",
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.path_prefix = path_prefix
        # Mapping: (client_ip, prefix) -> list of request timestamps
        self._requests: dict[tuple[str, str], list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not path.startswith(self.path_prefix):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, self.path_prefix)
        now = time.time()
        cutoff = now - self.window_seconds

        # Prune old timestamps
        timestamps = [t for t in self._requests[key] if t > cutoff]
        self._requests[key] = timestamps

        if len(timestamps) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(self.window_seconds)},
            )

        self._requests[key].append(now)
        return await call_next(request)
