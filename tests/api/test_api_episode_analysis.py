"""Asking a model about one episode, and the four gates before it is asked.

Every test here is about a refusal, because the route's job is mostly
refusing. What it must never do is refuse **everything**: a reader who
may not be shown a model's answer is still owed the verdict, the
diagnoses and the differences, and a route that returned nothing would
have made the model the feature rather than the layer over it.

The provider is the deterministic mock this deployment falls back to
without a key, so these run offline and cost nothing.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_api_episode_verdict import candidate, episode_row, seed

API = "/api/v1"


@pytest.fixture(autouse=True)
def _reset_process_state() -> Any:
    """One ledger and one registry per process, so tests must clear them."""
    from planbench_api.routers import decisions as router

    router._SPEND = type(router._SPEND)()
    router._IN_FLIGHT = type(router._IN_FLIGHT)()
    yield


def configure(mode: str, **overrides: Any) -> None:
    """Point the settings cache at a deployment that allows `mode`."""
    from planbench_api.config import get_settings

    settings = get_settings()
    object.__setattr__(settings, "episode_analyst_mode", mode)
    for field, value in overrides.items():
        object.__setattr__(settings, field, value)


def analyse(client: TestClient, run_id: str, episode: str, headers) -> Any:  # type: ignore[no-untyped-def]
    return client.post(
        f"{API}/decisions/{run_id}/episodes/{episode}/analysis",
        headers=headers,
        json={},
    )


def seeded(app, run_id: str) -> None:  # type: ignore[no-untyped-def]
    seed(
        app,
        run_id,
        candidates=[
            candidate("winner", [episode_row("ep00", 0.88)]),
            candidate("runner_up", [episode_row("ep00", 0.71)], global_planner="rrtstar"),
        ],
    )


def scripted_provider(monkeypatch: Any, *hypotheses: dict[str, Any]) -> None:
    """Point the route at a model that answers the shape it was asked for.

    The deployment's offline default is a keyword responder: it returns
    prose, the parser refuses it, and the round ends in `model_failed` —
    which is correct behaviour and useless for testing everything after
    the round.
    """
    from planbench_agent.provider import LLMResponse, MockProvider
    from planbench_api.routers import decisions as router

    answer = LLMResponse(
        structured={"abstained": False, "hypotheses": list(hypotheses)},
        input_tokens=1200,
        output_tokens=340,
    )

    class Agent:
        provider = MockProvider(script=[answer])

    monkeypatch.setattr(router, "get_agent_service", lambda *_, **__: Agent())


def hypothesis(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "bearing": "diagnosis",
        "decision": "no_check",
        "statement": "the runner up stalled where the winner did not",
        "proposition_type": "local_minimum_entrapment",
        "subject": "local_controller",
        "supports": [],
        "contradicts": [],
        "missing_evidence": [],
        "recommended_experiments": [],
    }
    base.update(overrides)
    return base


class TestTheDeploymentDecidesWhetherAModelIsAsked:
    def test_a_build_that_said_nothing_answers_404(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """Off is the default, and off is a 404 rather than an empty
        answer: the feature is absent here, not broken."""
        configure("off")
        seeded(app, "run_ep_off")
        assert analyse(client, "run_ep_off", "ep00", alice_headers).status_code == 404

    def test_the_verdict_route_beside_it_still_answers(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        configure("off")
        seeded(app, "run_ep_off_verdict")
        response = client.get(
            f"{API}/decisions/run_ep_off_verdict/episodes/ep00/verdict",
            headers=alice_headers,
        )
        assert response.status_code == 200
        assert response.json()["verdict"]["winner"] == "winner"

    def test_production_is_refused_in_this_build(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """The mode exists so granting it later is a grant and not a
        redesign. No episode gate decision can be issued yet."""
        configure("production")
        seeded(app, "run_ep_prod")
        response = analyse(client, "run_ep_prod", "ep00", alice_headers)
        assert response.status_code == 409
        assert "gate decision" in response.json()["error"]["message"]

    def test_preview_without_a_report_is_refused(
        self, client: TestClient, app, alice_headers: dict[str, str]
    ) -> None:
        """A mode that turned on with nothing behind it would be a
        decision nobody recorded."""
        configure("internal_preview", episode_analyst_report_ref="")
        seeded(app, "run_ep_preview_bare")
        response = analyse(client, "run_ep_preview_bare", "ep00", alice_headers)
        assert response.status_code == 409
        assert "evaluation report" in response.json()["error"]["message"]


class TestTheDeterministicHalfIsAlwaysServed:
    def test_shadow_runs_the_round_and_shows_nobody_the_answer(
        self, client: TestClient, app, alice_headers: dict[str, str], tmp_path
    ) -> None:
        configure("shadow", episode_analyst_artifact_root=str(tmp_path))
        seeded(app, "run_ep_shadow")
        response = analyse(client, "run_ep_shadow", "ep00", alice_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["model"] is None, "shadow shows a model's answer to nobody"
        assert body["verdict"]["winner"] == "winner"
        assert body["diagnoses"], "the deterministic half is served either way"

    def test_shadow_leaves_an_artifact_to_read_it_by(
        self, client: TestClient, app, monkeypatch, alice_headers: dict[str, str], tmp_path
    ) -> None:
        """A mode that ran a model and kept no record of it would be
        spending for nothing."""
        configure("shadow", episode_analyst_artifact_root=str(tmp_path))
        seeded(app, "run_ep_shadow_artifact")
        scripted_provider(monkeypatch, hypothesis())
        analyse(client, "run_ep_shadow_artifact", "ep00", alice_headers)
        written = list(tmp_path.rglob("*.json"))
        assert written, "shadow wrote no artifact"

    def test_preview_shows_an_administrator_the_answer(
        self, client: TestClient, app, monkeypatch, admin_headers: dict[str, str], tmp_path
    ) -> None:
        configure(
            "internal_preview",
            episode_analyst_report_ref="docs/journal/antongduy/reports/2026-08-27/…",
            episode_analyst_artifact_root=str(tmp_path),
        )
        seeded(app, "run_ep_preview_admin")
        scripted_provider(monkeypatch, hypothesis())
        body = analyse(client, "run_ep_preview_admin", "ep00", admin_headers).json()
        assert body["model"] is not None
        assert "response" in body["model"]

    def test_preview_shows_everybody_else_the_deterministic_half(
        self, client: TestClient, app, alice_headers: dict[str, str], tmp_path
    ) -> None:
        configure(
            "internal_preview",
            episode_analyst_report_ref="docs/journal/antongduy/reports/2026-08-27/…",
            episode_analyst_artifact_root=str(tmp_path),
        )
        seeded(app, "run_ep_preview_reader")
        body = analyse(client, "run_ep_preview_reader", "ep00", alice_headers).json()
        assert body["model"] is None
        assert body["verdict"]["winner"] == "winner"


class TestTheSameQuestionAskedAtOnce:
    """Dedup coalesces **concurrent** requests. It is not a cache: a
    request arriving after the first has finished runs its own round,
    and pretending otherwise would serve a stale explanation as a fresh
    one."""

    def test_the_second_caller_waits_for_the_first_answer(self) -> None:
        from planbench_api.episode_analysis import InFlightRegistry

        registry = InFlightRegistry()
        slot, owned = registry.start("k")
        assert owned

        second, owned_again = registry.start("k")
        assert not owned_again
        assert second is slot, "both callers wait on the one round"

        registry.finish("k", answer={"response": {}}, error=None)
        assert slot.done.is_set()
        assert slot.answer == {"response": {}}

    def test_a_request_after_the_round_finished_owns_its_own(self) -> None:
        from planbench_api.episode_analysis import InFlightRegistry

        registry = InFlightRegistry()
        registry.start("k")
        registry.finish("k", answer={"response": {}}, error=None)
        _, owned = registry.start("k")
        assert owned, "dedup is in-flight, not a cache"

    def test_two_different_questions_do_not_coalesce(self) -> None:
        from planbench_api.episode_analysis import InFlightRegistry, dedup_key

        first = dedup_key(packet_checksum="a", runtime_config_checksum="x")
        second = dedup_key(packet_checksum="a", runtime_config_checksum="y")
        assert first != second, "the same facts under another arm vector is another system"

        registry = InFlightRegistry()
        registry.start(first)
        _, owned = registry.start(second)
        assert owned


class TestWhatItSpends:
    def test_a_caller_past_the_daily_cap_is_refused(
        self, client: TestClient, app, monkeypatch, admin_headers: dict[str, str], tmp_path
    ) -> None:
        configure(
            "internal_preview",
            episode_analyst_report_ref="ref",
            episode_analyst_artifact_root=str(tmp_path),
            episode_analyst_max_calls_per_day=1,
        )
        seeded(app, "run_ep_cap_a")
        seeded(app, "run_ep_cap_b")
        scripted_provider(monkeypatch, hypothesis())
        assert analyse(client, "run_ep_cap_a", "ep00", admin_headers).status_code == 200
        second = analyse(client, "run_ep_cap_b", "ep00", admin_headers)
        assert second.status_code == 409
        assert "today" in second.json()["error"]["message"]


class TestWhatTheAuditRecords:
    def test_it_names_the_prompt_and_the_configuration_it_ran_under(
        self, client: TestClient, app, monkeypatch, admin_headers: dict[str, str], tmp_path
    ) -> None:
        configure(
            "internal_preview",
            episode_analyst_report_ref="ref",
            episode_analyst_artifact_root=str(tmp_path),
        )
        seeded(app, "run_ep_audit")
        scripted_provider(monkeypatch, hypothesis())
        body = analyse(client, "run_ep_audit", "ep00", admin_headers).json()
        audit = body["audit"]
        assert audit["prompt_checksum"]
        assert audit["runtime_config_checksum"]
        assert audit["packet_checksum"]

    def test_a_provider_that_fails_costs_the_reader_nothing(
        self, client: TestClient, app, admin_headers: dict[str, str], tmp_path, monkeypatch
    ) -> None:
        """The round is the layer on top. Losing it must not lose the
        verdict underneath."""
        from planbench_api.routers import decisions as router

        def explode(*_: Any, **__: Any) -> Any:
            raise RuntimeError("the provider is unreachable")

        configure(
            "internal_preview",
            episode_analyst_report_ref="ref",
            episode_analyst_artifact_root=str(tmp_path),
        )
        seeded(app, "run_ep_provider_down")
        monkeypatch.setattr(
            "planbench_analyst.episode_runner.run_episode_round", explode, raising=True
        )
        body = analyse(client, "run_ep_provider_down", "ep00", admin_headers).json()
        assert body["model"] is None
        assert body["verdict"]["winner"] == "winner"
        assert "model_failed" in body["audit"]
        assert router is not None
