"""In-memory gateway used by the agent tests.

Real enough to exercise the policy (states, transitions, missing ids)
without a database or an HTTP app, and small enough that a test can put
it into any state in two lines.
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
from planbench_benchmark import (
    AlgorithmAggregate,
    AlgorithmSpec,
    BenchmarkReport,
    BenchmarkSpec,
    Confidence,
    Evidence,
    FailureCategory,
    FailureReport,
    FairnessRecord,
    Finding,
    build_scenario,
)
from planbench_schemas.episode import EpisodeStatus


def sample_report(algorithms: tuple[str, ...] = ("astar+dwa", "astar+ppo")) -> BenchmarkReport:
    """A minimal but structurally real report (no fabricated episodes)."""
    map_data, scenario = build_scenario("open_space")
    seeds = (1, 2)
    return BenchmarkReport(
        spec=BenchmarkSpec(
            name="fake",
            algorithms=tuple(AlgorithmSpec(id=algorithm) for algorithm in algorithms),
            seeds=seeds,
        ),
        fairness=FairnessRecord.build(map_data, scenario, seeds),
        runs=(),
        aggregates=tuple(
            AlgorithmAggregate(
                algorithm=algorithm,
                episodes=2,
                success_rate=1.0 if index == 0 else 0.5,
                collision_rate=0.0 if index == 0 else 0.5,
                timeout_rate=0.0,
                stuck_rate=0.0,
                no_progress_rate=0.0,
                no_global_path_rate=0.0,
                mean_travel_time_successful=12.5 + index,
                worst_min_clearance=0.4 - 0.1 * index,
            )
            for index, algorithm in enumerate(algorithms)
        ),
    )


class FakeGateway:
    """Implements :class:`planbench_agent.gateway.AgentGateway`."""

    def __init__(self) -> None:
        self.benchmarks: dict[str, BenchmarkSummary] = {}
        self.reports: dict[str, BenchmarkReport] = {}
        self.episodes: dict[str, list[EpisodeSummary]] = {}
        self.runs: list[str] = []
        self._counter = 0

    # -- helpers for tests ------------------------------------------------

    def add_benchmark(
        self,
        benchmark_id: str = "a1b2c3d4e5f6",
        state: str = "draft",
        algorithms: tuple[str, ...] = ("astar+dwa", "astar+ppo"),
        with_report: bool = False,
        with_episodes: bool = False,
    ) -> BenchmarkSummary:
        summary = BenchmarkSummary(
            id=benchmark_id,
            name=f"benchmark {benchmark_id}",
            state=state,
            map_id="map1",
            scenario_id="scen1",
            scenario_name="open_space",
            algorithms=algorithms,
            seeds=(1, 2),
            created_by="op-alice",
        )
        self.benchmarks[benchmark_id] = summary
        if with_report:
            report = sample_report(algorithms)
            self.reports[benchmark_id] = report
            self.benchmarks[benchmark_id] = summary.model_copy(
                update={"conditions_checksum": report.fairness.conditions_checksum}
            )
        if with_episodes:
            self.episodes[benchmark_id] = [
                EpisodeSummary(
                    id=f"e9{index:010d}",
                    benchmark_id=benchmark_id,
                    algorithm=algorithms[index % len(algorithms)],
                    seed=1 + index,
                    status="success" if index == 0 else "collision",
                    reason="goal reached" if index == 0 else "collision with static obstacle",
                    travel_time=11.0 + index,
                    trajectory_length=9.0 + index,
                    min_clearance=0.35 - 0.1 * index,
                    artifact_uri=f"file://artifacts/{benchmark_id}/e9{index:010d}.json",
                )
                for index in range(2)
            ]
        return self.benchmarks[benchmark_id]

    def set_state(self, benchmark_id: str, state: str) -> BenchmarkSummary:
        current = self._require(benchmark_id)
        self.benchmarks[benchmark_id] = current.model_copy(update={"state": state})
        return self.benchmarks[benchmark_id]

    def _require(self, benchmark_id: str) -> BenchmarkSummary:
        try:
            return self.benchmarks[benchmark_id]
        except KeyError:
            raise GatewayError(f"benchmark {benchmark_id!r} not found") from None

    # -- AgentGateway -----------------------------------------------------

    def list_scenarios(self) -> list[ScenarioSummary]:
        return [
            ScenarioSummary(
                name="open_space",
                description="empty arena",
                curriculum_index=0,
                dynamic_obstacles=0,
                timeout_seconds=60.0,
            ),
            ScenarioSummary(
                name="doorway",
                description="1.6 m gap",
                curriculum_index=4,
                dynamic_obstacles=0,
                timeout_seconds=90.0,
            ),
        ]

    def list_algorithms(self) -> list[AlgorithmSummary]:
        return [
            AlgorithmSummary(id="astar+dwa", description="A* + DWA", benchmarkable=True),
            AlgorithmSummary(id="astar+ppo", description="A* + PPO", benchmarkable=True),
            AlgorithmSummary(
                id="astar+pure_pursuit", description="reference adapter", benchmarkable=False
            ),
        ]

    def list_benchmarks(self) -> list[BenchmarkSummary]:
        return sorted(self.benchmarks.values(), key=lambda item: item.id)

    def get_benchmark(self, benchmark_id: str) -> BenchmarkSummary:
        return self._require(benchmark_id)

    def get_report(self, benchmark_id: str) -> BenchmarkReport | None:
        self._require(benchmark_id)
        return self.reports.get(benchmark_id)

    def list_episodes(self, benchmark_id: str) -> list[EpisodeSummary]:
        self._require(benchmark_id)
        return list(self.episodes.get(benchmark_id, ()))

    def analyse_episode(self, episode_id: str) -> FailureReport:
        for episodes in self.episodes.values():
            for episode in episodes:
                if episode.id == episode_id:
                    return _analysis(episode)
        raise GatewayError(f"episode {episode_id!r} not found")

    def leaderboard(self, scenario_name: str | None = None) -> list[LeaderboardRow]:
        rows = [
            LeaderboardRow(
                algorithm=aggregate.algorithm,
                benchmark_id=benchmark_id,
                conditions_checksum=report.fairness.conditions_checksum,
                scenario_name=report.fairness.scenario_name,
                episodes=aggregate.episodes,
                success_rate=aggregate.success_rate,
                collision_rate=aggregate.collision_rate,
                overall_score=aggregate.success_rate,
            )
            for benchmark_id, report in self.reports.items()
            for aggregate in report.aggregates
        ]
        if scenario_name:
            rows = [row for row in rows if row.scenario_name == scenario_name]
        return rows

    def create_benchmark(self, draft: MissionDraft) -> BenchmarkSummary:
        self._counter += 1
        benchmark_id = f"cd{self._counter:010d}"
        summary = BenchmarkSummary(
            id=benchmark_id,
            name=draft.name,
            state="draft",
            map_id=f"map-{benchmark_id}",
            scenario_id=f"scenario-{benchmark_id}",
            scenario_name=draft.scenario,
            algorithms=draft.algorithms,
            seeds=draft.seeds,
            created_by="op-alice",
        )
        self.benchmarks[benchmark_id] = summary
        return summary

    def submit_benchmark(self, benchmark_id: str) -> BenchmarkSummary:
        self._require(benchmark_id)
        return self.set_state(benchmark_id, "pending_approval")

    def run_benchmark(self, benchmark_id: str) -> BenchmarkSummary:
        current = self._require(benchmark_id)
        if current.state != "approved":
            raise ApprovalRequired(f"benchmark {benchmark_id!r} is {current.state!r}")
        self.runs.append(benchmark_id)
        report = sample_report(current.algorithms)
        self.reports[benchmark_id] = report
        self.benchmarks[benchmark_id] = current.model_copy(
            update={
                "state": "pending_review",
                "conditions_checksum": report.fairness.conditions_checksum,
            }
        )
        return self.benchmarks[benchmark_id]


def _analysis(episode: EpisodeSummary) -> FailureReport:
    if episode.status == "success":
        return FailureReport(
            status=EpisodeStatus.SUCCESS,
            primary=Finding(
                category=FailureCategory.NONE,
                confidence=Confidence.HIGH,
                summary="episode reached the goal",
                evidence=(Evidence(kind="status", detail="engine recorded success"),),
            ),
        )
    return FailureReport(
        status=EpisodeStatus.COLLISION,
        primary=Finding(
            category=FailureCategory.STATIC_OBSTACLE_COLLISION,
            confidence=Confidence.HIGH,
            summary="robot hit a static obstacle",
            evidence=(
                Evidence(kind="collision_event", detail="collision at t=4.2 s", time=4.2),
                Evidence(kind="clearance", detail="clearance fell to 0.0 m", value=0.0),
            ),
        ),
    )


__all__ = ["FakeGateway", "sample_report"]
