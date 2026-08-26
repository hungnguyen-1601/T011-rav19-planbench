"""The model may add judgement; it may not remove an objection.

Every test here is about a way the model could make the critique worse
rather than better. The happy path — a model that reads the run and adds
a real finding — is one test. The other nine are the failure modes,
because those are what decide whether a reviewer can trust the output
without re-deriving it.

The provider is scripted throughout. What is under test is the leash,
not the model: given a response, does the wrapper keep the rules, drop
the fabrications, and say what it dropped.
"""

from __future__ import annotations

from typing import Any

import pytest

from planbench_agent.critique import MAX_MODEL_FINDINGS, critique_schema, critique_with_model
from planbench_agent.provider import LLMRequest, LLMResponse, MockProvider


def report() -> dict[str, Any]:
    """A run with exactly two rule findings, both about G4."""
    return {
        "identity": {
            "task_profile_id": "open_hall_v2",
            "sensor_noise": {"lidar_range_sigma_m": 0.02},
            "git_sha": "64d86d5f",
        },
        "sample": {
            "n_episodes": 30,
            "n_episodes_requested": 30,
            "interrupted": False,
            "n_min_required": 30,
        },
        "early_stop": {"stopped": []},
        "candidates": [
            {
                "candidate_id": "aaa",
                "stack_label": "astar+dwa",
                "cleared_gates": True,
                "blocking_gates": [],
                "success_rate": 0.9,
                "gates": {
                    "G2": {"n_runs": 30, "n_distinct_episodes": 30},
                    "G4": {"status": "screened_on_host", "p99_ms": 6.1, "threshold_ms": 50.0},
                    "G5": {"status": "estimated_from_structure"},
                },
            },
            {
                "candidate_id": "bbb",
                "stack_label": "rrtstar+dwa",
                "cleared_gates": True,
                "blocking_gates": [],
                "success_rate": 0.8,
                "gates": {
                    "G2": {"n_runs": 30, "n_distinct_episodes": 30},
                    "G4": {"status": "screened_on_host", "p99_ms": 9.4, "threshold_ms": 50.0},
                    "G5": {"status": "estimated_from_structure"},
                },
            },
        ],
        "measurement_environment": {"warning": None},
        "decision_card": {
            "status": "CLEAR_RECOMMENDATION",
            "tie_break_reason": None,
            "evidence": {"ci95": [0.03, 0.04], "effect_size": 4.7, "n_episodes": 30},
        },
        "why_no_card": None,
    }


def scripted(payload: Any) -> MockProvider:
    """A provider that returns exactly ``payload`` as structured output."""

    class _Scripted(MockProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:  # noqa: ARG002
            return LLMResponse(structured=payload, model="scripted")

    return _Scripted()


def exploding(message: str = "connection reset") -> MockProvider:
    class _Boom(MockProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:  # noqa: ARG002
            raise RuntimeError(message)

    return _Boom()


def _ok(**overrides: Any) -> dict[str, Any]:
    payload = {
        "summary": "Both stacks were only ever screened on the benchmark host.",
        "findings": [],
        "ranked_rule_codes": ["G4_HOST_ONLY"],
    }
    payload.update(overrides)
    return payload


class TestTheRulesSurviveEverything:
    """Rule findings are the floor. Nothing the model does lowers it."""

    def test_a_provider_that_raises_still_yields_the_rules(self) -> None:
        result = critique_with_model(report(), exploding())
        assert [f.code for f in result.findings] == ["G4_HOST_ONLY", "G4_HOST_ONLY"]
        assert all(f.source == "rule" for f in result.findings)
        assert "provider failed" in result.refused

    def test_unstructured_output_still_yields_the_rules(self) -> None:
        result = critique_with_model(report(), scripted(None))
        assert len(result.findings) == 2
        assert result.refused

    def test_malformed_structured_output_still_yields_the_rules(self) -> None:
        result = critique_with_model(report(), scripted({"summary": 42}))
        assert len(result.findings) == 2
        assert "did not validate" in result.refused

    def test_a_model_that_omits_a_rule_code_cannot_drop_it(self) -> None:
        """Ranking is not filtering.

        A model that leaves a finding out of `ranked_rule_codes` has
        expressed an opinion about order, not a veto. Both rule findings
        must still come back.
        """
        result = critique_with_model(report(), scripted(_ok(ranked_rule_codes=[])))
        assert len([f for f in result.findings if f.source == "rule"]) == 2


class TestFabricatedCitationsAreDroppedAndCounted:
    def test_a_finding_citing_a_missing_field_is_dropped(self) -> None:
        payload = _ok(
            findings=[
                {
                    "code": "MADE_UP",
                    "severity": "blocking",
                    "kind": "present",
                    "claim": "x",
                    "ground": "y",
                    "field_path": "sample.no_such_field",
                    "suggested_check": "z",
                }
            ]
        )
        result = critique_with_model(report(), scripted(payload))
        assert result.fabricated == 1
        assert all(f.source == "rule" for f in result.findings)

    def test_a_finding_citing_a_real_field_is_kept_and_labelled(self) -> None:
        payload = _ok(
            findings=[
                {
                    "code": "BASELINE_IS_WEAK",
                    "severity": "material",
                    "kind": "omission",
                    "claim": "beating this baseline means something",
                    "ground": "the runner-up is the same controller config as the winner",
                    "field_path": "candidates[1].stack_label",
                    "suggested_check": "add a tuned baseline",
                }
            ]
        )
        result = critique_with_model(report(), scripted(payload))
        added = [f for f in result.findings if f.source == "model"]
        assert len(added) == 1
        assert added[0].code == "BASELINE_IS_WEAK"
        assert result.fabricated == 0

    def test_the_count_is_published_not_swallowed(self) -> None:
        """Two invented findings is a measurement, not an embarrassment."""
        bad = {
            "code": "X",
            "severity": "blocking",
            "kind": "present",
            "claim": "a",
            "ground": "b",
            "field_path": "nowhere.at.all",
            "suggested_check": "c",
        }
        result = critique_with_model(report(), scripted(_ok(findings=[bad, dict(bad, code="Y")])))
        assert result.fabricated == 2


class TestBannedLanguageIsRefused:
    def test_calling_a_stack_safe_drops_the_prose_not_the_rules(self) -> None:
        """The contract's ban applies to the critic too (§17).

        The rules still come back — dropping them would punish the
        reviewer for the model's mistake.
        """
        result = critique_with_model(
            report(), scripted(_ok(summary="astar+dwa is an toàn for this deployment."))
        )
        assert result.refused
        assert result.summary == ""
        assert len([f for f in result.findings if f.source == "rule"]) == 2


class TestTheModelIsCapped:
    def test_no_more_than_the_ceiling_is_accepted(self) -> None:
        many = [
            {
                "code": f"C{i}",
                "severity": "disclosure",
                "kind": "present",
                "claim": "a",
                "ground": "b",
                "field_path": "sample.n_episodes",
                "suggested_check": "c",
            }
            for i in range(MAX_MODEL_FINDINGS + 4)
        ]
        result = critique_with_model(report(), scripted(_ok(findings=many)))
        assert len([f for f in result.findings if f.source == "model"]) == MAX_MODEL_FINDINGS

    def test_the_schema_states_the_same_ceiling(self) -> None:
        assert critique_schema()["properties"]["findings"]["maxItems"] == MAX_MODEL_FINDINGS


class TestTheSchemaConstrainsWhatCanComeBack:
    def test_severity_and_kind_are_enumerated(self) -> None:
        """The cheapest guardrail: a compliant provider cannot invent one."""
        item = critique_schema()["properties"]["findings"]["items"]["properties"]
        assert item["severity"]["enum"] == ["blocking", "material", "disclosure"]
        assert item["kind"]["enum"] == ["present", "omission"]

    def test_ranked_codes_are_restricted_to_known_rules(self) -> None:
        from planbench_decision.self_check import RULE_CODES

        assert set(critique_schema()["properties"]["ranked_rule_codes"]["items"]["enum"]) == set(
            RULE_CODES
        )

    def test_extra_properties_are_forbidden(self) -> None:
        schema = critique_schema()
        assert schema["additionalProperties"] is False
        assert schema["properties"]["findings"]["items"]["additionalProperties"] is False


class TestProvenanceIsCarried:
    def test_the_result_says_which_model_spoke(self) -> None:
        result = critique_with_model(report(), scripted(_ok()))
        assert result.provider
        assert result.deterministic is True  # MockProvider

    def test_a_clean_run_with_a_silent_model_says_nothing(self) -> None:
        """The false-alarm floor, with the model in the loop."""
        clean = report()
        for candidate in clean["candidates"]:
            candidate["gates"]["G4"]["status"] = "confirmed_on_target"
        result = critique_with_model(clean, scripted(_ok(summary="", ranked_rule_codes=[])))
        assert result.findings == ()
        assert result.summary == ""
        assert result.fabricated == 0


@pytest.mark.parametrize("path", ["sample.n_episodes", "candidates[0].gates.G4.status"])
def test_the_prompt_shows_the_paths_it_asks_for(path: str) -> None:
    """The system prompt's examples must be paths that actually resolve.

    An example the model copies verbatim and gets dropped for would
    teach exactly the wrong lesson.
    """
    from planbench_agent.critique import CRITIQUE_SYSTEM
    from planbench_decision.self_check import resolve

    assert path in CRITIQUE_SYSTEM
    assert resolve(report(), path) is not None
