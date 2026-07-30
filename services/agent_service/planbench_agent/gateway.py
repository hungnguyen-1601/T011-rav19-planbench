"""The narrow port between the agent and the rest of PlanBench.

The agent service must not import the FastAPI application: that would
invert the dependency (core-first) and make every agent test require an
HTTP app. Instead it declares the operations it needs as a Protocol, and
``planbench_api.agent_gateway`` supplies the adapter.

Two consequences worth stating:

- The tool surface is exactly this protocol. There is deliberately no
  method for driving the robot, writing ``/cmd_vel``, editing a map, or
  approving a benchmark — the agent physically cannot reach them.
- Tests substitute a fake gateway and exercise the whole agent, tool
  policy included, without a server.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from planbench_agent.specs import MissionDraft
from planbench_benchmark import BenchmarkReport, FailureReport


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    curriculum_index: int
    dynamic_obstacles: int
    timeout_seconds: float


class AlgorithmSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    description: str
    benchmarkable: bool


class BenchmarkSummary(BaseModel):
    """Enough of a benchmark for the agent to reason and cite."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    state: str
    map_id: str
    scenario_id: str
    scenario_name: str | None = None
    algorithms: tuple[str, ...] = ()
    seeds: tuple[int, ...] = ()
    created_by: str = ""
    conditions_checksum: str | None = None
    report_artifact_uri: str | None = None


class EpisodeSummary(BaseModel):
    """One episode, identified so a report can cite it."""

    model_config = ConfigDict(frozen=True)

    id: str
    benchmark_id: str
    algorithm: str
    seed: int
    status: str
    reason: str
    travel_time: float | None = None
    trajectory_length: float | None = None
    min_clearance: float | None = None
    artifact_uri: str | None = None


class LeaderboardRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    algorithm: str
    benchmark_id: str
    conditions_checksum: str
    scenario_name: str
    episodes: int
    success_rate: float
    collision_rate: float
    overall_score: float | None = None


class GatewayError(Exception):
    """The requested resource does not exist or the call was rejected."""


class ApprovalRequired(GatewayError):
    """Refused: a human reviewer has not approved this benchmark.

    Raised *before* anything executes. This is gate 1 of the two
    mandatory human gates, enforced on the agent's own side so the
    refusal is visible in the transcript rather than buried in an HTTP
    status code.
    """


@runtime_checkable
class AgentGateway(Protocol):
    """Everything the agent is allowed to do to PlanBench."""

    # -- read -----------------------------------------------------------
    def list_scenarios(self) -> list[ScenarioSummary]: ...

    def list_algorithms(self) -> list[AlgorithmSummary]: ...

    def list_benchmarks(self) -> list[BenchmarkSummary]: ...

    def get_benchmark(self, benchmark_id: str) -> BenchmarkSummary: ...

    def get_report(self, benchmark_id: str) -> BenchmarkReport | None: ...

    def list_episodes(self, benchmark_id: str) -> list[EpisodeSummary]: ...

    def analyse_episode(self, episode_id: str) -> FailureReport: ...

    def leaderboard(self, scenario_name: str | None = None) -> list[LeaderboardRow]: ...

    # -- write (policy-gated) --------------------------------------------
    def create_benchmark(self, draft: MissionDraft) -> BenchmarkSummary:
        """Create a DRAFT benchmark. Drafting is not execution."""
        ...

    def submit_benchmark(self, benchmark_id: str) -> BenchmarkSummary:
        """Send a draft to a human reviewer. Still not execution."""
        ...

    def run_benchmark(self, benchmark_id: str) -> BenchmarkSummary:
        """Execute an already-APPROVED benchmark, or raise ApprovalRequired."""
        ...


__all__ = [
    "AgentGateway",
    "AlgorithmSummary",
    "ApprovalRequired",
    "BenchmarkSummary",
    "EpisodeSummary",
    "GatewayError",
    "LeaderboardRow",
    "ScenarioSummary",
]
