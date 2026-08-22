"""Smoke tests for the LangGraph scaffold under `src/`.

Skipped unless the scaffold's dependencies are installed. `langgraph`,
`langchain-openai` and `pytest-asyncio` are not in `requirements.txt`,
because PlanBench itself does not use `src/` — it is the T-011 starter
template that came with the repository.

Installing those packages is not enough to make these tests pass:
`agent.ainvoke` calls OpenAI, so they also need a real `OPENAI_API_KEY`
and network access. They are therefore not runnable in CI, and no
placeholder key is set there to pretend otherwise.
"""

import pytest

pytest.importorskip("langgraph", reason="LangGraph scaffold dependencies are not installed")
pytest.importorskip("pytest_asyncio", reason="pytest-asyncio is not installed")

from src.agents.graph import agent  # noqa: E402


@pytest.mark.asyncio
async def test_agent_basic_flow():
    result = await agent.ainvoke({"query": "Hello"})
    assert "response" in result


@pytest.mark.asyncio
async def test_agent_state_structure():
    result = await agent.ainvoke({"query": "Test query"})
    assert isinstance(result, dict)
    assert "query" in result
