"""Tool registry, effect policy, and the approval gate.

These are the tests that matter most for M8: they encode what the agent
is not allowed to do.
"""

from __future__ import annotations

import json

import pytest
from agent_fakes import FakeGateway

from planbench_agent.gateway import AgentGateway, ApprovalRequired
from planbench_agent.provider import ToolCall
from planbench_agent.rag import KnowledgeBase, split_markdown
from planbench_agent.tools import (
    FORBIDDEN_CAPABILITIES,
    RUNNABLE_STATE,
    Effect,
    ToolPolicy,
    build_registry,
)


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def knowledge() -> KnowledgeBase:
    return KnowledgeBase(
        split_markdown(
            "FAIRNESS.md",
            "# Fairness\nAll algorithms run under one conditions_checksum.\n"
            "# Approval\nA reviewer must approve a benchmark before it runs.\n",
        )
    )


# Positional-only so a tool argument literally called "name" does not
# collide with this helper's own parameter.
def call(tool: str, /, **arguments) -> ToolCall:
    return ToolCall(id="c1", name=tool, arguments=arguments)


class TestSurface:
    def test_fake_gateway_satisfies_the_protocol(self, gateway):
        assert isinstance(gateway, AgentGateway)

    def test_no_tool_grants_a_forbidden_capability(self, gateway, knowledge):
        names = set(build_registry(gateway, knowledge).names())
        assert names.isdisjoint(FORBIDDEN_CAPABILITIES)
        # And nothing that merely smells like actuation or approval.
        assert not [
            name
            for name in names
            if any(word in name for word in ("cmd_vel", "drive", "approve", "accept"))
        ]

    def test_gateway_protocol_has_no_actuation_method(self):
        forbidden = {"drive", "cmd_vel", "step", "approve", "accept_result"}
        assert forbidden.isdisjoint(dir(AgentGateway))

    def test_search_tool_appears_only_with_a_corpus(self, gateway, knowledge):
        assert "search_knowledge" not in build_registry(gateway).names()
        assert "search_knowledge" in build_registry(gateway, knowledge).names()

    def test_tool_order_is_stable(self, gateway, knowledge):
        first = build_registry(gateway, knowledge).specs()
        second = build_registry(gateway, knowledge).specs()
        assert [tool.name for tool in first] == [tool.name for tool in second]

    def test_every_schema_forbids_extra_properties(self, gateway, knowledge):
        for spec in build_registry(gateway, knowledge).specs():
            assert spec.input_schema["additionalProperties"] is False, spec.name


class TestReadTools:
    def test_returns_json_for_a_list_of_models(self, gateway):
        registry = build_registry(gateway)
        payload = json.loads(registry.execute(call("list_algorithms")).content)
        assert {item["id"] for item in payload} == {
            "astar+dwa",
            "astar+ppo",
            "astar+pure_pursuit",
        }

    def test_missing_benchmark_is_an_error_result_not_an_exception(self, gateway):
        # The model should see the failure and correct itself; raising
        # here would kill the loop instead.
        result = build_registry(gateway).execute(call("get_benchmark", benchmark_id="nope"))
        assert result.is_error and "not found" in result.content

    def test_unknown_tool_is_reported_with_the_available_set(self, gateway):
        result = build_registry(gateway).execute(call("delete_everything"))
        assert result.is_error and "unknown tool" in result.content

    def test_search_returns_citable_chunk_ids(self, gateway, knowledge):
        registry = build_registry(gateway, knowledge)
        payload = json.loads(
            registry.execute(call("search_knowledge", query="conditions_checksum")).content
        )
        assert payload[0]["citation_id"].startswith("document:FAIRNESS.md#")

    def test_search_says_nothing_matched_rather_than_inventing(self, gateway, knowledge):
        registry = build_registry(gateway, knowledge)
        result = registry.execute(call("search_knowledge", query="quantum teleportation"))
        assert "do not answer from memory" in result.content


class TestPolicy:
    def test_read_only_sessions_block_write_tools(self, gateway):
        registry = build_registry(gateway, policy=ToolPolicy(allow_write=False))
        assert "run_benchmark" not in [tool.name for tool in registry.specs()]
        result = registry.execute(call("run_benchmark", benchmark_id="a1b2c3d4e5f6"))
        assert result.is_error and "read-only" in result.content

    def test_read_tools_survive_a_read_only_policy(self, gateway):
        registry = build_registry(gateway, policy=ToolPolicy(allow_write=False))
        assert "list_scenarios" in [tool.name for tool in registry.specs()]

    def test_effects_are_classified_correctly(self, gateway):
        registry = build_registry(gateway)
        effects = {tool.name: tool.effect for tool in registry.available()}
        assert effects["run_benchmark"] is Effect.WRITE
        assert effects["propose_benchmark"] is Effect.WRITE
        assert effects["get_leaderboard"] is Effect.READ

    def test_episode_budget_caps_an_oversized_proposal(self, gateway):
        registry = build_registry(gateway, policy=ToolPolicy(max_episodes=4))
        result = registry.execute(
            call(
                "propose_benchmark",
                name="huge",
                scenario="doorway",
                algorithms=["astar+dwa"],
                seeds=list(range(1, 11)),
            )
        )
        assert result.is_error and "exceeds the per-benchmark limit" in result.content
        assert gateway.benchmarks == {}


class TestProposal:
    def test_valid_proposal_drafts_and_submits_but_does_not_run(self, gateway):
        registry = build_registry(gateway)
        payload = json.loads(
            registry.execute(
                call(
                    "propose_benchmark",
                    name="doorway run",
                    scenario="doorway",
                    algorithms=["astar+dwa"],
                    seeds=[1, 2],
                )
            ).content
        )
        assert payload["benchmark"]["state"] == "pending_approval"
        assert "cannot approve" in payload["next_step"]
        assert gateway.runs == []

    def test_unknown_scenario_is_refused_before_anything_is_created(self, gateway):
        result = build_registry(gateway).execute(
            call(
                "propose_benchmark",
                name="x",
                scenario="mars_colony",
                algorithms=["astar+dwa"],
                seeds=[1],
            )
        )
        assert result.is_error and "unknown scenario" in result.content
        assert gateway.benchmarks == {}

    def test_stack_needing_a_checkpoint_cannot_be_proposed(self, gateway):
        # The agent has no way to know which trained model to load, so
        # offering astar+ppo here would invite a fabricated path.
        result = build_registry(gateway).execute(
            call(
                "propose_benchmark",
                name="x",
                scenario="doorway",
                algorithms=["astar+ppo"],
                seeds=[1],
            )
        )
        assert result.is_error and "model_path" in result.content
        assert gateway.benchmarks == {}

    def test_reference_adapter_cannot_be_proposed(self, gateway):
        result = build_registry(gateway).execute(
            call(
                "propose_benchmark",
                name="x",
                scenario="doorway",
                algorithms=["astar+pure_pursuit"],
                seeds=[1],
            )
        )
        assert result.is_error and "reference adapter" in result.content


class TestApprovalGate:
    @pytest.mark.parametrize(
        "state", ["draft", "pending_approval", "running", "completed", "rejected"]
    )
    def test_run_is_refused_in_every_unapproved_state(self, gateway, state):
        gateway.add_benchmark("a1b2c3d4e5f6", state=state)
        result = build_registry(gateway).execute(call("run_benchmark", benchmark_id="a1b2c3d4e5f6"))
        assert result.is_error
        assert "refused" in result.content and RUNNABLE_STATE in result.content
        assert gateway.runs == []

    def test_run_proceeds_once_a_human_has_approved(self, gateway):
        gateway.add_benchmark("a1b2c3d4e5f6", state="approved")
        result = build_registry(gateway).execute(call("run_benchmark", benchmark_id="a1b2c3d4e5f6"))
        assert not result.is_error
        assert gateway.runs == ["a1b2c3d4e5f6"]
        assert json.loads(result.content)["state"] == "pending_review"

    def test_gateway_refuses_even_if_the_tool_check_is_bypassed(self, gateway):
        # Defence in depth: the tool checks the state, and so does the
        # gateway. Removing either one must still leave a gate.
        gateway.add_benchmark("a1b2c3d4e5f6", state="draft")
        with pytest.raises(ApprovalRequired):
            gateway.run_benchmark("a1b2c3d4e5f6")

    def test_results_land_in_review_not_accepted(self, gateway):
        gateway.add_benchmark("a1b2c3d4e5f6", state="approved")
        finished = gateway.run_benchmark("a1b2c3d4e5f6")
        assert finished.state == "pending_review"  # gate 2 is still ahead
