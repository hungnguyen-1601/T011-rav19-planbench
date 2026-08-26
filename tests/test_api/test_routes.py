"""Route tests for the T-011 scaffold's FastAPI app under `src/`.

Skipped unless the scaffold's dependencies are installed. `langgraph` and
`pytest-asyncio` are not in `requirements.txt`, because PlanBench does not
use `src/` — it is the starter template that came with the repository.

These three routes do not call the LLM, so they need no API key: once the
packages are installed the tests exercise the app over an in-process ASGI
transport, with no network. The `client` fixture is in `conftest.py`
beside this file.
"""

import pytest

pytest.importorskip("langgraph", reason="LangGraph scaffold dependencies are not installed")
pytest.importorskip("pytest_asyncio", reason="pytest-asyncio is not installed")


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    response = await client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
