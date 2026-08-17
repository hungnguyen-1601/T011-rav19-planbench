"""The tool surface, and the authority it does not have.

Most of these assert absences. That is deliberate: what keeps an agent
from running a comparison or approving a result is that no such method
exists, and an absence is only guaranteed if something fails when it
stops being one.

The rest check that a tool failure comes back to the model as a message
it can act on. A loop that crashes on a bad id teaches the model nothing;
one that answers "not found" lets it correct itself.
"""

from __future__ import annotations

import json

import pytest
from agent_fakes import FakeGateway, populated_gateway

from planbench_agent.gateway import AgentGateway
from planbench_agent.provider import ToolCall
from planbench_agent.rag import KnowledgeBase, split_markdown
from planbench_agent.tools import (
    FORBIDDEN_CAPABILITIES,
    Effect,
    ToolPolicy,
    build_registry,
)


@pytest.fixture
def registry():
    return build_registry(populated_gateway())


def call(registry, name: str, **arguments):
    return registry.execute(ToolCall(id="c1", name=name, arguments=arguments))


class TestTheAgentCannotAct:
    def test_no_tool_mutates_anything(self, registry) -> None:
        """The whole surface is READ. There is no write path to gate."""
        assert all(tool.effect is Effect.READ for tool in registry.available())

    def test_the_forbidden_list_names_no_tool(self, registry) -> None:
        assert FORBIDDEN_CAPABILITIES.isdisjoint(set(registry.names()))

    def test_the_gateway_protocol_has_no_actuation_or_approval(self) -> None:
        """Checked on the Protocol, not on one implementation.

        A fake that simply omitted a dangerous method would prove
        nothing; the guarantee has to hold for anything satisfying the
        port.
        """
        surface = set(AgentGateway.__annotations__) | {
            name for name in dir(AgentGateway) if not name.startswith("_")
        }
        for forbidden in ("drive", "cmd_vel", "approve", "accept", "reject", "run_"):
            assert not any(forbidden in name for name in surface), forbidden

    def test_running_a_comparison_is_named_as_forbidden(self) -> None:
        """It became impossible; the list records that it is also intended."""
        assert "run_comparison" in FORBIDDEN_CAPABILITIES
        assert "approve_run" in FORBIDDEN_CAPABILITIES


class TestTheSurfaceMatchesTheCurrentArchitecture:
    def test_it_reaches_the_decision_layer(self, registry) -> None:
        names = set(registry.names())
        assert {
            "list_deployments",
            "list_decision_runs",
            "get_decision_run",
            "get_gate_table",
            "get_critique",
        } <= names

    def test_no_tool_points_at_the_retired_benchmark_flow(self, registry) -> None:
        """P6 removed those pages; a tool for them would produce answers
        about a system nobody can open."""
        names = set(registry.names())
        assert (
            not {
                "list_benchmarks",
                "get_benchmark",
                "get_benchmark_report",
                "get_leaderboard",
                "propose_benchmark",
                "run_benchmark",
            }
            & names
        )

    def test_every_tool_declares_a_closed_schema(self, registry) -> None:
        """additionalProperties:false is the cheapest guardrail there is."""
        for tool in registry.available():
            assert tool.input_schema.get("additionalProperties") is False, tool.name


class TestReadingWorks:
    def test_it_lists_deployments(self, registry) -> None:
        payload = json.loads(call(registry, "list_deployments").content)
        assert payload[0]["task_profile_id"] == "hall_v1"

    def test_it_returns_a_report_whole(self, registry) -> None:
        """Whole because findings cite paths into it.

        A summary here would make an honest citation unresolvable at the
        other end.
        """
        payload = json.loads(call(registry, "get_decision_run", run_id="run001").content)
        assert payload["sample"]["n_episodes"] == 30
        assert payload["candidates"][0]["gates"]["G2"]["n_min"] == 30

    def test_the_gate_table_says_whose_gates_they_are(self, registry) -> None:
        rows = json.loads(call(registry, "get_gate_table", run_id="run001").content)
        assert {row["stack_label"] for row in rows} == {"astar+dwa", "rrtstar+dwa"}
        assert all("gates" in row for row in rows)

    def test_the_critique_tool_returns_the_rules_findings(self) -> None:
        """So the model can add to them instead of restating them."""
        gateway = FakeGateway()
        gateway.add_deployment()
        gateway.add_run("bad", n_episodes=12)
        findings = json.loads(call(build_registry(gateway), "get_critique", run_id="bad").content)
        assert any(item["code"] == "SAMPLE_BELOW_N_MIN" for item in findings)

    def test_a_clean_run_yields_no_objections(self, registry) -> None:
        assert json.loads(call(registry, "get_critique", run_id="run001").content) == []


class TestFailuresComeBackAsMessages:
    def test_an_unknown_run_is_an_error_result_not_an_exception(self, registry) -> None:
        result = call(registry, "get_decision_run", run_id="nope")
        assert result.is_error
        assert "not found" in result.content

    def test_an_unknown_tool_lists_the_real_ones(self, registry) -> None:
        result = call(registry, "no_such_tool")
        assert result.is_error
        assert "list_deployments" in result.content

    def test_a_missing_argument_is_reported_not_raised(self, registry) -> None:
        assert call(registry, "get_decision_run").is_error


class TestKnowledgeSearch:
    @staticmethod
    def _registry_with_docs():
        base = KnowledgeBase(
            split_markdown(
                "CONTRACTS.md",
                "# G2\nZero collisions over at least N_min distinct episodes.\n",
            )
        )
        return build_registry(populated_gateway(), base)

    def test_hits_carry_a_citable_id(self) -> None:
        hits = json.loads(call(self._registry_with_docs(), "search_knowledge", query="G2").content)
        assert hits[0]["citation_id"] == "document:CONTRACTS.md#1"

    def test_a_miss_says_so_rather_than_inviting_a_guess(self) -> None:
        result = call(self._registry_with_docs(), "search_knowledge", query="quantum tunnelling")
        assert "do not answer from memory" in result.content

    def test_the_tool_is_absent_when_no_corpus_is_configured(self, registry) -> None:
        assert "search_knowledge" not in registry.names()


class TestPolicy:
    def test_a_read_only_policy_changes_nothing_because_all_tools_read(self) -> None:
        registry = build_registry(populated_gateway(), policy=ToolPolicy(allow_write=False))
        assert len(registry.available()) == len(registry.names())

    def test_tool_order_is_stable(self) -> None:
        """The tool list is part of the prompt prefix; reordering it
        would change the prompt for no reason."""
        first = build_registry(populated_gateway()).names()
        second = build_registry(populated_gateway()).names()
        assert first == second == tuple(sorted(first))
