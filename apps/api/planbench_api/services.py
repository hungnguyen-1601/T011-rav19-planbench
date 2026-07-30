"""Service layer: domain orchestration between routers and repositories.

Routers hold no simulation logic; everything domain-shaped lives here
or in the core packages.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from planbench_api.approval import Action, ApprovalRecord, TransitionError, next_state
from planbench_api.auth import User
from planbench_api.errors import DomainValidationError, InvalidStateError, NotFoundError
from planbench_api.repositories import (
    RepositoryHub,
    StoredBenchmark,
    StoredMap,
    StoredScenario,
    StoredSimulation,
)
from planbench_api.worker import Job, JobQueue
from planbench_benchmark import (
    AlgorithmSpec,
    BenchmarkSpec,
    build_local_planner,
    list_algorithms,
    run_benchmark,
    validate_algorithm_config,
)
from planbench_benchmark.registry import AlgorithmConfigError, UnknownAlgorithmError
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.nav_stack import StackRun, run_stack
from planbench_tracking import ExperimentTracker, NullTracker

logger = logging.getLogger("planbench.api.services")


class BenchmarkCancelled(Exception):
    """Raised inside the run loop when an operator cancels mid-benchmark."""


DEFAULT_ALGORITHM = "astar+dwa"


def require_algorithm(algorithm: str, config: dict | None = None) -> None:
    """Validate an algorithm id and its config, as domain errors."""
    try:
        validate_algorithm_config(algorithm, config)
    except UnknownAlgorithmError as exc:
        raise DomainValidationError(str(exc)) from exc
    except AlgorithmConfigError as exc:
        raise DomainValidationError(str(exc)) from exc


class MapService:
    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def create(self, map_data: MapData) -> StoredMap:
        return self._repos.maps.create(map_data)

    def get(self, map_id: str) -> StoredMap:
        return self._repos.maps.get(map_id)

    def list(self) -> list[StoredMap]:
        return self._repos.maps.list()

    def update(self, map_id: str, map_data: MapData) -> StoredMap:
        return self._repos.maps.update(map_id, map_data)

    def delete(self, map_id: str) -> None:
        self._repos.maps.delete(map_id)

    def validate(self, map_data: MapData) -> list[str]:
        """Semantic checks beyond schema validation (schema ran at parse)."""
        errors: list[str] = []
        if not any(value == 0 for value in map_data.cells):
            errors.append("map has no free cells")
        return errors


class ScenarioService:
    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def create(self, map_id: str, scenario: Scenario) -> StoredScenario:
        stored_map = self._repos.maps.get(map_id)
        errors = self.validate_against_map(stored_map.map_data, scenario)
        if errors:
            raise DomainValidationError("scenario is invalid for this map", errors)
        return self._repos.scenarios.create(map_id, scenario)

    def get(self, scenario_id: str) -> StoredScenario:
        return self._repos.scenarios.get(scenario_id)

    def list(self) -> list[StoredScenario]:
        return self._repos.scenarios.list()

    def update(self, scenario_id: str, map_id: str, scenario: Scenario) -> StoredScenario:
        stored_map = self._repos.maps.get(map_id)
        errors = self.validate_against_map(stored_map.map_data, scenario)
        if errors:
            raise DomainValidationError("scenario is invalid for this map", errors)
        return self._repos.scenarios.update(scenario_id, map_id, scenario)

    def delete(self, scenario_id: str) -> None:
        self._repos.scenarios.delete(scenario_id)

    @staticmethod
    def validate_against_map(map_data: MapData, scenario: Scenario) -> list[str]:
        """Reuse the engine's placement validation; return errors as a list."""
        engine = SimulationEngine()
        engine.load_map(map_data)
        try:
            engine.load_scenario(scenario)
        except ValueError as exc:
            return [str(exc)]
        return []


class SimulationService:
    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def create(
        self, map_id: str, scenario_id: str, algorithm: str, config: dict | None = None
    ) -> StoredSimulation:
        require_algorithm(algorithm, config)
        stored_map = self._repos.maps.get(map_id)
        stored_scenario = self._repos.scenarios.get(scenario_id)
        errors = ScenarioService.validate_against_map(stored_map.map_data, stored_scenario.scenario)
        if errors:
            raise DomainValidationError("scenario is invalid for this map", errors)
        return self._repos.simulations.create(map_id, scenario_id, algorithm, config or {})

    def get(self, simulation_id: str) -> StoredSimulation:
        return self._repos.simulations.get(simulation_id)

    def list(self) -> list[StoredSimulation]:
        return self._repos.simulations.list()

    def run(self, simulation_id: str) -> StoredSimulation:
        stored = self._repos.simulations.get(simulation_id)
        if stored.state == "finished":
            raise InvalidStateError(f"simulation {simulation_id!r} already finished")
        map_data = self._repos.maps.get(stored.map_id).map_data
        scenario = self._repos.scenarios.get(stored.scenario_id).scenario
        planner = build_local_planner(stored.algorithm, stored.config)
        stack_run: StackRun = run_stack(map_data, scenario, planner)
        logger.info(
            "simulation finished",
            extra={
                "context": {
                    "simulation_id": simulation_id,
                    "algorithm": stored.algorithm,
                    "status": stack_run.result.status.value,
                    "steps": stack_run.result.steps,
                }
            },
        )
        return self._repos.simulations.set_finished(simulation_id, stack_run)


class BenchmarkService:
    """Benchmark orchestration over the core engine.

    M4 scope: sequential execution inside the request, plus the approval
    state machine. Background workers and parallelism arrive in M5.

    Running is gated on the APPROVED state, so an unapproved spec can
    never execute (spec section 21, gate 1).
    """

    def __init__(
        self,
        repos: RepositoryHub,
        tracker: ExperimentTracker | None = None,
        jobs: JobQueue | None = None,
    ) -> None:
        self._repos = repos
        self._tracker = tracker or NullTracker()
        self._jobs = jobs

    def transition(
        self, benchmark_id: str, action: Action, user: User, comment: str = ""
    ) -> StoredBenchmark:
        """Apply a lifecycle action, recording an approval entry."""
        stored = self._repos.benchmarks.get(benchmark_id)
        try:
            target = next_state(
                stored.state,
                action,
                user.role,
                actor=user.username,
                created_by=stored.created_by,
            )
        except TransitionError as exc:
            raise InvalidStateError(str(exc)) from exc
        record = ApprovalRecord(
            benchmark_id=benchmark_id,
            user=user.username,
            role=user.role,
            action=action,
            previous_state=stored.state,
            new_state=target,
            comment=comment,
            timestamp=datetime.now(UTC).isoformat(),
        )
        logger.info(
            "benchmark transition",
            extra={
                "context": {
                    "benchmark_id": benchmark_id,
                    "action": action.value,
                    "from": stored.state.value,
                    "to": target.value,
                    "user": user.username,
                }
            },
        )
        return self._repos.benchmarks.set_state(benchmark_id, target, record)

    def create(
        self,
        name: str,
        map_id: str,
        scenario_id: str,
        algorithms: list[AlgorithmSpec],
        seeds: list[int],
        created_by: str,
        description: str = "",
    ) -> StoredBenchmark:
        for algorithm in algorithms:
            require_algorithm(algorithm.id, algorithm.config)
        self._repos.maps.get(map_id)
        self._repos.scenarios.get(scenario_id)
        try:
            spec = BenchmarkSpec(
                name=name,
                description=description,
                algorithms=tuple(algorithms),
                seeds=tuple(seeds),
            )
        except ValueError as exc:
            raise DomainValidationError("invalid benchmark spec", [str(exc)]) from exc
        return self._repos.benchmarks.create(spec, map_id, scenario_id, created_by)

    def get(self, benchmark_id: str) -> StoredBenchmark:
        return self._repos.benchmarks.get(benchmark_id)

    def list(self) -> list[StoredBenchmark]:
        return self._repos.benchmarks.list()

    def run(
        self,
        benchmark_id: str,
        user: User,
        on_progress: Callable[[int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> StoredBenchmark:
        """Execute an APPROVED benchmark; store the report and episodes.

        The RUN transition itself enforces approval: a DRAFT or
        PENDING_APPROVAL benchmark raises before any episode executes.
        """
        stored = self.transition(benchmark_id, Action.RUN, user)
        map_data = self._repos.maps.get(stored.map_id).map_data
        scenario = self._repos.scenarios.get(stored.scenario_id).scenario

        # Episodes are persisted as they finish, so replay works without
        # re-running anything and the report itself stays metrics-only.
        finished = 0

        def store_episode(record, stack_run: StackRun) -> None:
            nonlocal finished
            self._repos.episodes.create(
                benchmark_id, record.algorithm, record.seed, stack_run, record
            )
            finished += 1
            if on_progress is not None:
                on_progress(finished)
            if should_cancel is not None and should_cancel():
                raise BenchmarkCancelled(f"benchmark {benchmark_id!r} cancelled by operator")

        try:
            report = run_benchmark(map_data, scenario, stored.spec, on_run=store_episode)
        except BenchmarkCancelled:
            self.transition(benchmark_id, Action.CANCEL, user, comment="cancelled during run")
            raise
        except Exception:
            self.transition(benchmark_id, Action.FAIL, user, comment="execution error")
            raise
        logger.info(
            "benchmark finished",
            extra={
                "context": {
                    "benchmark_id": benchmark_id,
                    "episodes": len(report.runs),
                    "conditions_checksum": report.fairness.conditions_checksum,
                }
            },
        )
        self._repos.benchmarks.set_report(benchmark_id, report)
        # Tracking must never break a benchmark: build_tracker degrades to
        # a null tracker when MLflow is unavailable.
        self._tracker.log_benchmark(benchmark_id, report, {"created_by": stored.created_by})
        # Results now await the second human gate (Reviewer accept/reject).
        return self.transition(benchmark_id, Action.COMPLETE, user)


class BenchmarkJobService:
    """Runs approved benchmarks on the bounded background worker.

    The approval gate is applied *before* queueing, so an unapproved
    benchmark never reaches the worker. Cancellation is cooperative: the
    worker stops between episodes so recorded results stay consistent.
    """

    def __init__(self, benchmarks: BenchmarkService, jobs: JobQueue) -> None:
        self._benchmarks = benchmarks
        self._jobs = jobs

    def start(self, benchmark_id: str, user: User) -> Job:
        stored = self._benchmarks.get(benchmark_id)
        episodes = len(stored.spec.algorithms) * len(stored.spec.seeds)

        def work(job: Job) -> None:
            self._benchmarks.run(
                benchmark_id,
                user,
                on_progress=lambda done: _report(job, done),
                should_cancel=lambda: self._jobs.is_cancelled(job.id),
            )

        def _report(job: Job, done: int) -> None:
            job.progress = done
            job.message = f"{done}/{job.total} episodes finished"

        return self._jobs.submit(benchmark_id, "benchmark", work, total=episodes)

    def status(self, benchmark_id: str) -> Job | None:
        return self._jobs.get(benchmark_id)

    def cancel(self, benchmark_id: str) -> bool:
        return self._jobs.cancel(benchmark_id)


class EpisodeService:
    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def get(self, episode_id: str):
        return self._repos.episodes.get(episode_id)

    def list_for_benchmark(self, benchmark_id: str):
        self._repos.benchmarks.get(benchmark_id)  # 404 if unknown
        return self._repos.episodes.list_for_benchmark(benchmark_id)


def algorithms_catalogue():
    """Registered stacks, for the /algorithms endpoint."""
    return list_algorithms()


__all__ = [
    "DEFAULT_ALGORITHM",
    "BenchmarkService",
    "EpisodeService",
    "MapService",
    "NotFoundError",
    "ScenarioService",
    "SimulationService",
    "algorithms_catalogue",
    "require_algorithm",
]
