"""Unit tests for Rate Limiting middleware."""

import time
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from planbench_api.middleware.rate_limit import RateLimiterMiddleware


def test_rate_limiter_allows_under_limit():
    """Verify requests under the limit succeed."""
    app = FastAPI()
    app.add_middleware(RateLimiterMiddleware, max_requests=3, window_seconds=60, path_prefix="/test-limit")

    @app.get("/test-limit")
    def endpoint():
        return {"status": "ok"}

    client = TestClient(app)
    for _ in range(3):
        response = client.get("/test-limit")
        assert response.status_code == 200


def test_rate_limiter_blocks_over_limit():
    """Verify exceeding the rate limit returns HTTP 429 Too Many Requests."""
    app = FastAPI()
    app.add_middleware(RateLimiterMiddleware, max_requests=2, window_seconds=60, path_prefix="/test-block")

    @app.get("/test-block")
    def endpoint():
        return {"status": "ok"}

    client = TestClient(app)
    assert client.get("/test-block").status_code == 200
    assert client.get("/test-block").status_code == 200

    # 3rd request exceeds limit
    blocked = client.get("/test-block")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert "too many requests" in blocked.text.lower()
