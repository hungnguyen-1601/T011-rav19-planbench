"""The model may rank and extend advice; it may never overrule it.

Same constitution as the critique layer, tested the same way: the
deterministic floor survives every model behaviour — a good answer, a
hallucinated citation, a forgotten code, an invented one, a dead
provider — and the reader can always tell which half said what.
"""

from __future__ import annotations

from typing import Any

from planbench_agent.advisor import MAX_MODEL_ADVICE, advise_with_model
from planbench_agent.provider import LLMRequest, LLMResponse, MockProvider
from planbench_decision.advice import Advice

SOURCE: dict[str, Any] = {
    "report": {"candidates": [{"candidate_id": "abc", "success_rate": 0.7}]},
    "task_profile": {"constraints": {"success_rate_min": 0.85}},
}

RULES = (
    Advice(
        code="GA_G3_SUCCESS_RATE",
        kind="diagnosis",
        severity="blocking",
        claim="astar+dwa reached the goal 70% of the time against 85% required",
        ground="G3 is the deployment's own floor",
        field_path="report.candidates[0].success_rate",
        do="read the failure reasons per episode before tuning",
        do_not="lower success_rate_min to obtain a Decision Card",
    ),
    Advice(
        code="GA_G4_HOST_ONLY",
        kind="diagnosis",
        severity="disclosure",
        claim="G4 passed on a development host",
        ground="the gate records screened_on_host",
        field_path="report.candidates[0].candidate_id",
        do="say the latency result is a host screening",
        do_not="present it as a real-time guarantee",
    ),
)


def scripted(answer: Any) -> MockProvider:
    class _Scripted(MockProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:  # noqa: ARG002
            return LLMResponse(structured=answer, model="scripted")

    return _Scripted()


def answer(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "Fix G3 first; the latency pass is host-only.",
        "ranking": ["GA_G3_SUCCESS_RATE", "GA_G4_HOST_ONLY"],
        "additions": [],
    }
    base.update(overrides)
    return base


class TestTheFloorAlwaysSurvives:
    def test_every_rule_item_is_present_after_a_good_answer(self) -> None:
        result = advise_with_model("diagnosis", SOURCE, RULES, scripted(answer()))
        rule_codes = [a.code for a in result.advice if a.source == "rule"]
        assert sorted(rule_codes) == sorted(r.code for r in RULES)

    def test_a_forgotten_code_is_kept_at_the_end_not_dropped(self) -> None:
        result = advise_with_model(
            "diagnosis", SOURCE, RULES, scripted(answer(ranking=["GA_G4_HOST_ONLY"]))
        )
        codes = [a.code for a in result.advice if a.source == "rule"]
        assert codes == ["GA_G4_HOST_ONLY", "GA_G3_SUCCESS_RATE"]

    def test_an_invented_code_in_the_ranking_is_ignored(self) -> None:
        result = advise_with_model(
            "diagnosis", SOURCE, RULES, scripted(answer(ranking=["GA_MADE_UP"]))
        )
        assert len([a for a in result.advice if a.source == "rule"]) == len(RULES)

    def test_the_forbidden_move_survives_verbatim(self) -> None:
        result = advise_with_model("diagnosis", SOURCE, RULES, scripted(answer()))
        found = next(a for a in result.advice if a.code == "GA_G3_SUCCESS_RATE")
        assert found.do_not == "lower success_rate_min to obtain a Decision Card"

    def test_a_dead_provider_degrades_to_the_rules_alone(self) -> None:
        class _Boom(MockProvider):
            def complete(self, request: LLMRequest) -> LLMResponse:  # noqa: ARG002
                raise RuntimeError("connection reset")

        result = advise_with_model("diagnosis", SOURCE, RULES, _Boom())
        assert "provider failed" in result.refused
        assert len(result.advice) == len(RULES)

    def test_unstructured_output_degrades_the_same_way(self) -> None:
        result = advise_with_model("diagnosis", SOURCE, RULES, scripted(None))
        assert result.refused
        assert len(result.advice) == len(RULES)


class TestModelAdditionsAreHeldToTheRulesStandard:
    def test_a_grounded_addition_is_kept_and_tagged(self) -> None:
        extra = {
            "severity": "material",
            "claim": "only one candidate was measured",
            "ground": "the candidates list has a single entry",
            "field_path": "report.candidates[0].candidate_id",
            "do": "register a second candidate before comparing",
        }
        result = advise_with_model("diagnosis", SOURCE, RULES, scripted(answer(additions=[extra])))
        added = [a for a in result.advice if a.source == "model"]
        assert len(added) == 1
        assert added[0].kind == "diagnosis"
        assert result.fabricated == 0

    def test_a_citation_that_resolves_nowhere_is_dropped_and_counted(self) -> None:
        fake = {
            "severity": "blocking",
            "claim": "the map is corrupt",
            "ground": "invented",
            "field_path": "report.map.checksum",
            "do": "regenerate the map",
        }
        result = advise_with_model("diagnosis", SOURCE, RULES, scripted(answer(additions=[fake])))
        assert result.fabricated == 1
        assert not [a for a in result.advice if a.source == "model"]

    def test_the_additions_are_capped_by_the_schema(self) -> None:
        from planbench_agent.advisor import advisor_schema

        assert advisor_schema()["properties"]["additions"]["maxItems"] == MAX_MODEL_ADVICE

    def test_the_summary_comes_through(self) -> None:
        result = advise_with_model("diagnosis", SOURCE, RULES, scripted(answer()))
        assert "G3" in result.summary
