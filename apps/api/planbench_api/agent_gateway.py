"""Adapter implementing :class:`planbench_agent.gateway.AgentGateway`.

The dependency points this way on purpose: the API knows about the agent
package, the agent package knows nothing about FastAPI. Everything the
agent can reach is spelled out here, so widening its authority means
editing this file and nothing else.

The gateway runs as a specific user. Benchmarks the agent creates are
attributed to that user, which matters for separation of duties: the
approver must be somebody else, and the audit trail shows who asked.
"""

from __future__ import annotations

from planbench_agent.gateway import (
    AlgorithmSummary,
    ApprovalRequired,
    BenchmarkSummary,
    EpisodeSummary,
    GatewayError,
    LeaderboardRow,
    ScenarioSummary,
)
from planbench_agent.specs import MissionDraft
from planbench_api.approval import Action, BenchmarkState
from planbench_api.auth import User
from planbench_api.errors import NotFoundError
from planbench_api.leaderboard import build_leaderboard
from planbench_api.repositories import RepositoryHub, StoredBenchmark, StoredEpisode
from planbench_api.services import BenchmarkService, MapService, ScenarioService
from planbench_benchmark import (
    CURRICULUM_ORDER,
    AlgorithmSpec,
    BenchmarkReport,
    FailureReport,
    analyse_episode,
    build_scenario,
    list_algorithms,
)


class ApiAgentGateway:
    """Everything the agent may do, expressed over the existing services."""

    def __init__(
        self,
        repos: RepositoryHub,
        benchmarks: BenchmarkService,
        maps: MapService,
        scenarios: ScenarioService,
        user: User,
    ) -> None:
        self._repos = repos
        self._benchmarks = benchmarks
        self._maps = maps
        self._scenarios = scenarios
        self._user = user

    # -- read ------------------------------------------------------------

    def list_scenarios(self) -> list[ScenarioSummary]:
        summaries = []
        for index, name in enumerate(CURRICULUM_ORDER):
            _, scenario = build_scenario(name)
            summaries.append(
                ScenarioSummary(
                    name=name,
                    description=scenario.description,
                    curriculum_index=index,
                    dynamic_obstacles=len(scenario.dynamic_obstacles),
                    timeout_seconds=scenario.timeout_seconds,
                )
            )
        return summaries

    def list_algorithms(self) -> list[AlgorithmSummary]:
        return [
            AlgorithmSummary(
                id=info.id, description=info.description, benchmarkable=info.benchmarkable
            )
            for info in list_algorithms()
        ]

    def list_benchmarks(self) -> list[BenchmarkSummary]:
        return [self._summary(stored) for stored in self._repos.benchmarks.list()]

    def get_benchmark(self, benchmark_id: str) -> BenchmarkSummary:
        return self._summary(self._stored(benchmark_id))

    def get_report(self, benchmark_id: str) -> BenchmarkReport | None:
        return self._stored(benchmark_id).report

    def list_episodes(self, benchmark_id: str) -> list[EpisodeSummary]:
        self._stored(benchmark_id)  # 404 before returning an empty list
        return [
            self._episode(stored)
            for stored in self._repos.episodes.list_for_benchmark(benchmark_id)
        ]

    def analyse_episode(self, episode_id: str) -> FailureReport:
        try:
            stored = self._repos.episodes.get(episode_id)
        except NotFoundError as exc:
            raise GatewayError(str(exc)) from exc
        benchmark = self._stored(stored.benchmark_id)
        scenario = self._repos.scenarios.get(benchmark.scenario_id).scenario
        return analyse_episode(
            stored.run.result, scenario, min_clearance=stored.run.metrics.min_clearance
        )

    def leaderboard(self, scenario_name: str | None = None) -> list[LeaderboardRow]:
        board = build_leaderboard(
            self._repos.benchmarks.list(), scenario_name=scenario_name, accepted_only=True
        )
        return [
            LeaderboardRow(
                algorithm=entry.algorithm,
                benchmark_id=entry.benchmark_id,
                conditions_checksum=entry.conditions_checksum,
                scenario_name=entry.scenario_name,
                episodes=entry.episodes,
                success_rate=entry.success_rate,
                collision_rate=entry.collision_rate,
                overall_score=entry.overall_score,
            )
            for group in board.groups
            for entry in group.entries
        ]

    # -- write ------------------------------------------------------------

    def create_benchmark(self, draft: MissionDraft) -> BenchmarkSummary:
        """Materialise the library scenario, then create a DRAFT benchmark.

        The map and scenario come from :func:`build_scenario`, never from
        the model — the agent selects an existing entry by name and can
        supply no geometry of its own.
        """
        map_data, scenario = build_scenario(draft.scenario)
        stored_map = self._maps.create(map_data)
        stored_scenario = self._scenarios.create(stored_map.id, scenario)
        created = self._benchmarks.create(
            name=draft.name,
            map_id=stored_map.id,
            scenario_id=stored_scenario.id,
            algorithms=[AlgorithmSpec(id=algorithm) for algorithm in draft.algorithms],
            seeds=list(draft.seeds),
            created_by=self._user.username,
            description=draft.description,
        )
        return self._summary(created)

    def submit_benchmark(self, benchmark_id: str) -> BenchmarkSummary:
        stored = self._benchmarks.transition(
            benchmark_id, Action.SUBMIT, self._user, comment="submitted by the agent"
        )
        return self._summary(stored)

    def run_benchmark(self, benchmark_id: str) -> BenchmarkSummary:
        stored = self._stored(benchmark_id)
        if stored.state is not BenchmarkState.APPROVED:
            raise ApprovalRequired(
                f"benchmark {benchmark_id!r} is {stored.state.value!r}; a human reviewer "
                "must approve it before it can run"
            )
        return self._summary(self._benchmarks.run(benchmark_id, self._user))

    # -- mapping ------------------------------------------------------------

    def _stored(self, benchmark_id: str) -> StoredBenchmark:
        try:
            return self._repos.benchmarks.get(benchmark_id)
        except NotFoundError as exc:
            raise GatewayError(str(exc)) from exc

    def _summary(self, stored: StoredBenchmark) -> BenchmarkSummary:
        scenario_name = None
        if stored.report is not None:
            scenario_name = stored.report.fairness.scenario_name
        else:
            try:
                scenario_name = self._repos.scenarios.get(stored.scenario_id).scenario.name
            except NotFoundError:
                scenario_name = None
        return BenchmarkSummary(
            id=stored.id,
            name=stored.spec.name,
            state=stored.state.value,
            map_id=stored.map_id,
            scenario_id=stored.scenario_id,
            scenario_name=scenario_name,
            algorithms=tuple(algorithm.id for algorithm in stored.spec.algorithms),
            seeds=tuple(stored.spec.seeds),
            created_by=stored.created_by,
            conditions_checksum=(
                stored.report.fairness.conditions_checksum if stored.report else None
            ),
            report_artifact_uri=stored.report_artifact_uri,
        )

    @staticmethod
    def _episode(stored: StoredEpisode) -> EpisodeSummary:
        metrics = stored.record.metrics
        return EpisodeSummary(
            id=stored.id,
            benchmark_id=stored.benchmark_id,
            algorithm=stored.algorithm,
            seed=stored.seed,
            status=stored.record.status.value,
            reason=stored.record.reason,
            travel_time=metrics.travel_time,
            trajectory_length=metrics.trajectory_length,
            min_clearance=metrics.min_clearance,
            artifact_uri=stored.artifact_uri,
        )


__all__ = ["ApiAgentGateway"]
