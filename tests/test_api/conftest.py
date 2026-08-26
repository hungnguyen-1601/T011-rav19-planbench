"""Fixtures for the T-011 scaffold's API tests under `src/`.

The template shipped these tests with a `client` fixture, but the fixture
lived in a `tests/conftest.py` that did not survive the merge into
PlanBench — this repository already had one. Rather than merge two
unrelated conftests, the fixture is scoped to the directory that uses it.

Everything is imported inside the fixture body: `src.main` pulls in
LangGraph, which is not part of `requirements.txt`, and a conftest that
fails to import turns into a collection error instead of a clean skip.
The skip itself is declared in the test module.
"""

from __future__ import annotations

import pytest


@pytest.fixture
async def client():
    """Async HTTP client bound to the scaffold's FastAPI app, no network."""
    import httpx

    from src.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
