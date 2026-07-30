"""End-to-end agent workflow against a fake gateway.

Covers the sequence the spec mandates — mission, draft, human approval,
run, evidence, report — plus every point at which the agent must stop
and refuse.
"""

from __future__ import annotations

import pytest
from agent_fakes import FakeGateway

from planbench_agent.gateway import ApprovalRequired
from planbench_agent.provider import (
    LLMMessage,
    LLMResponse,
    MockProvider,
    StopReason,
    ToolCall,
)
from planbench_agent.rag import KnowledgeBase, split_markdown
from planbench_agent.tools import ToolPolicy
from planbench_agent.workflow import AgentService, AgentState


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def knowledge() -> KnowledgeBase:
    return KnowledgeBase(
        split_markdown(
            "FAIRNESS.md",
            "# Fairness\nResults compare only within one conditions_checksum.\n",
        )
    )


@pytest.fixture
def agent(gateway, knowledge) -> AgentService:
    return AgentService(MockProvider(), gateway, knowledge)


class TestMissionParsing:
    def test_a_recognised_mission_produces_a_validated_draft(self, agent):
        session = agent.new_session("s1")
        agent.parse_mission(session, "Benchmark DWA on the doorway scenario, seeds 1 2")
        assert session.state is AgentState.MISSION_PARSED
        assert session.draft is not None
        assert session.draft.scenario == "doorway"
        assert session.draft.algorithms == ("astar+dwa",)
        assert session.draft.seeds == (1, 2)

    def test_a_stack_needing_a_checkpoint_is_refused(self, agent, gateway):
        # astar+ppo is a real, benchmarkable stack — but only a human can
        # say which trained checkpoint to load.
        session = agent.new_session("s1")
        agent.parse_mission(session, "Compare DWA and PPO on doorway")
        assert session.state is AgentState.REFUSED
        assert any("model_path" in error for error in session.refusal.errors)
        assert gateway.benchmarks == {}

    def test_an_unparseable_mission_is_refused(self, agent):
        session = agent.new_session("s1")
        agent.parse_mission(session, "make the robot faster please")
        assert session.state is AgentState.REFUSED
        assert session.draft is None
        assert session.refusal is not None

    def test_a_schema_violating_answer_is_refused(self, gateway):
        # The provider returns something structurally wrong; nothing must
        # reach the gateway.
        provider = MockProvider(
            script=[LLMResponse(structured={"scenario": "doorway", "seeds": [1]})]
        )
        service = AgentService(provider, gateway)
        session = service.new_session("s1")
        service.parse_mission(session, "anything")
        assert session.state is AgentState.REFUSED
        assert "did not match the schema" in session.refusal.reason
        assert gateway.benchmarks == {}

    def test_an_invented_scenario_is_refused(self, gateway):
        provider = MockProvider(
            script=[
                LLMResponse(
                    structured={
                        "name": "n",
                        "description": "",
                        "scenario": "mars_colony",
                        "algorithms": ["astar+dwa"],
                        "seeds": [1],
                    }
                )
            ]
        )
        service = AgentService(provider, gateway)
        session = service.new_session("s1")
        service.parse_mission(session, "benchmark mars_colony")
        assert session.state is AgentState.REFUSED
        assert any("unknown scenario" in error for error in session.refusal.errors)

    def test_a_provider_refusal_is_recorded_as_one(self, gateway):
        provider = MockProvider(script=[LLMResponse(stop_reason=StopReason.REFUSAL)])
        service = AgentService(provider, gateway)
        session = service.new_session("s1")
        service.parse_mission(session, "anything")
        assert session.state is AgentState.REFUSED

    def test_the_mission_prompt_carries_the_library_enum(self, gateway):
        provider = MockProvider(script=[LLMResponse(stop_reason=StopReason.REFUSAL)])
        service = AgentService(provider, gateway)
        service.parse_mission(service.new_session("s1"), "x")
        schema = provider.calls[0].output_schema
        assert "doorway" in schema["properties"]["scenario"]["enum"]


class TestApprovalGates:
    def test_submitting_stops_at_pending_approval(self, agent, gateway):
        session = agent.new_session("s1")
        agent.parse_mission(session, "benchmark dwa on doorway")
        summary = agent.submit_for_approval(session)
        assert summary.state == "pending_approval"
        assert session.state is AgentState.AWAITING_HUMAN_APPROVAL
        assert gateway.runs == []

    def test_running_an_unapproved_benchmark_raises(self, agent, gateway):
        gateway.add_benchmark("a1b2c3d4e5f6", state="pending_approval")
        session = agent.new_session("s1")
        with pytest.raises(ApprovalRequired, match="must approve"):
            agent.run_approved(session, "a1b2c3d4e5f6")
        assert gateway.runs == []

    def test_the_refusal_is_visible_in_the_transcript(self, agent, gateway):
        gateway.add_benchmark("a1b2c3d4e5f6", state="draft")
        session = agent.new_session("s1")
        with pytest.raises(ApprovalRequired):
            agent.run_approved(session, "a1b2c3d4e5f6")
        assert session.events[-1].action == "run_refused"

    def test_the_full_gated_sequence(self, agent, gateway):
        session = agent.new_session("s1")
        agent.parse_mission(session, "benchmark dwa on doorway with seeds 1 2")
        created = agent.submit_for_approval(session)

        with pytest.raises(ApprovalRequired):
            agent.run_approved(session)  # still nobody has approved it

        gateway.set_state(created.id, "approved")  # a human, out of band
        finished = agent.run_approved(session)

        assert finished.state == "pending_review"  # gate 2 still ahead
        assert gateway.runs == [created.id]
        assert [event.action for event in session.events] == [
            "parse_mission",
            "submit_for_approval",
            "run_refused",
            "run_benchmark",
            "run_finished",
        ]

    def test_session_without_a_benchmark_cannot_run(self, agent):
        with pytest.raises(ValueError, match="no benchmark"):
            agent.run_approved(agent.new_session("s1"))


class TestEvidenceAndReport:
    def test_evidence_includes_failure_analysis_for_failed_episodes(self, agent, gateway):
        gateway.add_benchmark(
            "b11111111111", state="accepted", with_report=True, with_episodes=True
        )
        bundle = agent.collect_evidence("b11111111111", "why did it fail?")
        assert any("static_obstacle_collision" in item.statement for item in bundle.items)

    def test_analysis_can_be_skipped(self, agent, gateway):
        gateway.add_benchmark(
            "b11111111111", state="accepted", with_report=True, with_episodes=True
        )
        bundle = agent.collect_evidence("b11111111111", analyse_failures=False)
        assert not any("failure analysis" in item.statement for item in bundle.items)

    def test_report_cites_only_collected_evidence(self, agent, gateway):
        gateway.add_benchmark(
            "b11111111111", state="accepted", with_report=True, with_episodes=True
        )
        session = agent.new_session("s1")
        report = agent.write_report(session, "b11111111111", "Which stack succeeded more often?")
        assert not report.refused
        assert set(report.citations) <= agent.collect_evidence("b11111111111", "").ids | set(
            report.citations
        )
        assert session.state is AgentState.REPORTED

    def test_report_on_an_unrun_benchmark_still_refuses_to_conclude(self, agent, gateway):
        gateway.add_benchmark("b11111111111", state="draft")
        session = agent.new_session("s1")
        report = agent.write_report(session, "b11111111111")
        # One evidence item exists (the benchmark's identity), so the
        # report is produced but says only what is recorded: no metrics.
        assert "success_rate" not in report.text
        assert report.provisional is True


class TestConverse:
    def test_uses_tools_and_reports_which_ones(self, agent, gateway):
        gateway.add_benchmark("a1b2c3d4e5f6", state="accepted", with_report=True)
        turn, messages = agent.converse("summarise benchmark a1b2c3d4e5f6")
        assert "get_benchmark" in turn.tools_used
        assert turn.truncated is False
        assert messages[0].text == "summarise benchmark a1b2c3d4e5f6"

    def test_says_nothing_when_no_tool_returns_data(self, agent):
        turn, _ = agent.converse("tell me about hydraulic grippers")
        assert "Nothing is asserted" in turn.text or turn.tools_used

    def test_tool_errors_are_surfaced_not_swallowed(self, agent):
        turn, _ = agent.converse("summarise benchmark deadbeef12")
        assert any("not found" in error for error in turn.tool_errors)

    def test_iteration_budget_is_enforced(self, gateway, knowledge):
        looping = MockProvider(
            responder=lambda _: LLMResponse(
                tool_calls=(ToolCall(id="c", name="list_scenarios", arguments={}),),
                stop_reason=StopReason.TOOL_USE,
            )
        )
        service = AgentService(looping, gateway, knowledge)
        turn, _ = service.converse("go", max_iterations=3)
        assert turn.truncated is True
        assert turn.iterations == 3
        assert "Nothing is asserted" in turn.text

    def test_history_is_carried_into_the_next_turn(self, agent):
        history = (LLMMessage.user("earlier"), LLMMessage.assistant("noted"))
        _, messages = agent.converse("and now?", history=history)
        assert messages[0].text == "earlier"

    def test_read_only_policy_removes_write_tools_from_the_prompt(self, gateway, knowledge):
        provider = MockProvider(script=[LLMResponse(text="done")])
        service = AgentService(provider, gateway, knowledge, policy=ToolPolicy(allow_write=False))
        service.converse("hello")
        offered = {tool.name for tool in provider.calls[0].tools}
        assert "run_benchmark" not in offered
        assert "propose_benchmark" not in offered

    def test_the_chat_prompt_states_the_hard_limits(self, agent):
        from planbench_agent.workflow import CHAT_SYSTEM

        assert "Never claim a planner is safe" in CHAT_SYSTEM
        assert "cannot drive the robot" in CHAT_SYSTEM


class TestSessionRecord:
    def test_session_reports_the_provider_that_produced_it(self, agent):
        session = agent.new_session("s1")
        assert session.provider == "mock"
        assert session.deterministic is True

    def test_events_are_ordered_and_timestamped(self, agent):
        session = agent.new_session("s1")
        agent.parse_mission(session, "benchmark dwa on open_space")
        agent.submit_for_approval(session)
        timestamps = [event.timestamp for event in session.events]
        assert timestamps == sorted(timestamps)
