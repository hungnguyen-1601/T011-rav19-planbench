"""The chat surface of the recommendation: a read-only tool, mock-reachable.

What matters here is plumbing, not math — the rules themselves are
proven in ``test_recommendation.py`` against real report shapes. These
tests pin the guarantees the tool adds: it reads and only reads, the
deterministic mock can reach it by keyword so the offline path works,
and a gateway with several deployments refuses with names rather than
guessing which one the question meant.
"""

from __future__ import annotations

from agent_fakes import FakeGateway, populated_gateway

from planbench_agent.deterministic import _plan
from planbench_agent.gateway import GatewayError
from planbench_agent.tools import Effect, build_registry


class TestTheToolExists:
    def test_it_is_registered_and_read_only(self):
        registry = build_registry(populated_gateway())
        names = registry.names()
        assert "get_recommendation" in names
        tool = next(t for t in registry.available() if t.name == "get_recommendation")
        assert tool.effect is Effect.READ

    def test_every_tool_in_the_registry_still_only_reads(self):
        """The eleventh tool must not be the one that broke the rule."""
        registry = build_registry(populated_gateway())
        for tool in registry.available():
            assert tool.effect is Effect.READ, tool.name


class TestTheGatewayContract:
    def test_a_lone_deployment_is_resolved_without_an_id(self):
        gateway = populated_gateway()
        result = gateway.get_recommendation()
        assert result["task_profile_id"] == "hall_v1"
        assert set(result) >= {"evidence_tier", "runs_considered", "cases", "advice"}

    def test_several_deployments_refuse_with_names(self):
        gateway = FakeGateway()
        gateway.add_deployment("hall_v1")
        gateway.add_deployment("depot_v2")
        try:
            gateway.get_recommendation()
        except GatewayError as error:
            message = str(error)
            assert "hall_v1" in message and "depot_v2" in message
        else:  # pragma: no cover - the refusal is the contract
            raise AssertionError("two deployments must not silently pick one")


class TestTheMockCanReachIt:
    def test_choice_wording_routes_to_the_tool(self):
        plan = _plan("which algorithm should we use for this deployment?", "")
        assert ("get_recommendation", {}) in plan

    def test_vietnamese_wording_routes_too(self):
        plan = _plan("dự án tôi nên chọn thuật toán nào?", "")
        assert ("get_recommendation", {}) in plan

    def test_unrelated_wording_does_not(self):
        plan = _plan("show me the gate table of run deadbeefdead", "")
        assert ("get_recommendation", {}) not in plan
