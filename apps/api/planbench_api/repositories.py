"""In-memory repositories. Replaced by PostgreSQL in a later milestone.

Thread-safe via a per-repository lock; IDs are short uuid4 hex strings
(identity, not part of the deterministic simulation contract).

Large episode payloads (trajectories) are written to artifact storage;
the repositories keep metadata plus the artifact URI, mirroring the
target database design (decision D15).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from planbench_api.approval import ApprovalRecord, BenchmarkState
from planbench_api.artifacts import ArtifactStore
from planbench_api.errors import NotFoundError
from planbench_benchmark import BenchmarkReport, BenchmarkSpec, RunRecord
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import StackRun


def new_id() -> str:
    """Short opaque identity. Not part of the deterministic contract."""
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    """UTC ISO-8601. Both storage backends persist exactly this string."""
    return datetime.now(UTC).isoformat()


@dataclass
class StoredMap:
    id: str
    version: int
    created_at: str
    map_data: MapData


@dataclass
class StoredScenario:
    id: str
    version: int
    map_id: str
    created_at: str
    scenario: Scenario


@dataclass
class StoredSimulation:
    id: str
    map_id: str
    scenario_id: str
    algorithm: str
    config: dict
    created_at: str
    state: str = "created"  # created | finished
    run: StackRun | None = None


@dataclass
class StoredEpisode:
    id: str
    benchmark_id: str
    algorithm: str
    seed: int
    created_at: str
    record: RunRecord
    artifact_uri: str
    artifact_checksum: str
    artifact_bytes: int
    run: StackRun  # kept in memory for replay until PostgreSQL lands


@dataclass
class StoredBenchmark:
    id: str
    spec: BenchmarkSpec
    map_id: str
    scenario_id: str
    created_by: str
    created_at: str
    state: BenchmarkState = BenchmarkState.DRAFT
    report: BenchmarkReport | None = None
    approvals: list[ApprovalRecord] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    report_artifact_uri: str | None = None


class MapRepository:
    def __init__(self) -> None:
        self._items: dict[str, StoredMap] = {}
        self._lock = threading.Lock()

    def create(self, map_data: MapData) -> StoredMap:
        with self._lock:
            stored = StoredMap(id=new_id(), version=1, created_at=now_iso(), map_data=map_data)
            self._items[stored.id] = stored
            return stored

    def get(self, map_id: str) -> StoredMap:
        try:
            return self._items[map_id]
        except KeyError:
            raise NotFoundError("map", map_id) from None

    def list(self) -> list[StoredMap]:
        return sorted(self._items.values(), key=lambda m: m.created_at)

    def update(self, map_id: str, map_data: MapData) -> StoredMap:
        with self._lock:
            current = self.get(map_id)
            updated = StoredMap(
                id=current.id,
                version=current.version + 1,
                created_at=current.created_at,
                map_data=map_data,
            )
            self._items[map_id] = updated
            return updated

    def delete(self, map_id: str) -> None:
        with self._lock:
            if map_id not in self._items:
                raise NotFoundError("map", map_id)
            del self._items[map_id]


class ScenarioRepository:
    def __init__(self) -> None:
        self._items: dict[str, StoredScenario] = {}
        self._lock = threading.Lock()

    def create(self, map_id: str, scenario: Scenario) -> StoredScenario:
        with self._lock:
            stored = StoredScenario(
                id=new_id(), version=1, map_id=map_id, created_at=now_iso(), scenario=scenario
            )
            self._items[stored.id] = stored
            return stored

    def get(self, scenario_id: str) -> StoredScenario:
        try:
            return self._items[scenario_id]
        except KeyError:
            raise NotFoundError("scenario", scenario_id) from None

    def list(self) -> list[StoredScenario]:
        return sorted(self._items.values(), key=lambda s: s.created_at)

    def update(self, scenario_id: str, map_id: str, scenario: Scenario) -> StoredScenario:
        with self._lock:
            current = self.get(scenario_id)
            updated = StoredScenario(
                id=current.id,
                version=current.version + 1,
                map_id=map_id,
                created_at=current.created_at,
                scenario=scenario,
            )
            self._items[scenario_id] = updated
            return updated

    def delete(self, scenario_id: str) -> None:
        with self._lock:
            if scenario_id not in self._items:
                raise NotFoundError("scenario", scenario_id)
            del self._items[scenario_id]


class SimulationRepository:
    def __init__(self) -> None:
        self._items: dict[str, StoredSimulation] = {}
        self._lock = threading.Lock()

    def create(
        self, map_id: str, scenario_id: str, algorithm: str, config: dict
    ) -> StoredSimulation:
        with self._lock:
            stored = StoredSimulation(
                id=new_id(),
                map_id=map_id,
                scenario_id=scenario_id,
                algorithm=algorithm,
                config=config,
                created_at=now_iso(),
            )
            self._items[stored.id] = stored
            return stored

    def get(self, simulation_id: str) -> StoredSimulation:
        try:
            return self._items[simulation_id]
        except KeyError:
            raise NotFoundError("simulation", simulation_id) from None

    def list(self) -> list[StoredSimulation]:
        return sorted(self._items.values(), key=lambda s: s.created_at)

    def set_finished(self, simulation_id: str, run: StackRun) -> StoredSimulation:
        with self._lock:
            stored = self.get(simulation_id)
            stored.run = run
            stored.state = "finished"
            return stored


class EpisodeRepository:
    """Benchmark episodes; trajectories are persisted to artifact storage."""

    def __init__(self, artifacts: ArtifactStore) -> None:
        self._items: dict[str, StoredEpisode] = {}
        self._artifacts = artifacts
        self._lock = threading.Lock()

    def create(
        self, benchmark_id: str, algorithm: str, seed: int, run: StackRun, record: RunRecord
    ) -> StoredEpisode:
        episode_id = new_id()
        artifact = self._artifacts.write_episode(benchmark_id, episode_id, run)
        with self._lock:
            stored = StoredEpisode(
                id=episode_id,
                benchmark_id=benchmark_id,
                algorithm=algorithm,
                seed=seed,
                created_at=now_iso(),
                record=record,
                artifact_uri=artifact.uri,
                artifact_checksum=artifact.checksum,
                artifact_bytes=artifact.size_bytes,
                run=run,
            )
            self._items[episode_id] = stored
            return stored

    def get(self, episode_id: str) -> StoredEpisode:
        try:
            return self._items[episode_id]
        except KeyError:
            raise NotFoundError("episode", episode_id) from None

    def list_for_benchmark(self, benchmark_id: str) -> list[StoredEpisode]:
        return sorted(
            (e for e in self._items.values() if e.benchmark_id == benchmark_id),
            key=lambda e: e.record.episode_index,
        )


class BenchmarkRepository:
    def __init__(self, artifacts: ArtifactStore) -> None:
        self._items: dict[str, StoredBenchmark] = {}
        self._artifacts = artifacts
        self._lock = threading.Lock()

    def create(
        self, spec: BenchmarkSpec, map_id: str, scenario_id: str, created_by: str
    ) -> StoredBenchmark:
        with self._lock:
            stored = StoredBenchmark(
                id=new_id(),
                spec=spec,
                map_id=map_id,
                scenario_id=scenario_id,
                created_by=created_by,
                created_at=now_iso(),
            )
            self._items[stored.id] = stored
            return stored

    def get(self, benchmark_id: str) -> StoredBenchmark:
        try:
            return self._items[benchmark_id]
        except KeyError:
            raise NotFoundError("benchmark", benchmark_id) from None

    def list(self) -> list[StoredBenchmark]:
        return sorted(self._items.values(), key=lambda b: b.created_at)

    def set_state(
        self, benchmark_id: str, state: BenchmarkState, approval: ApprovalRecord | None = None
    ) -> StoredBenchmark:
        with self._lock:
            stored = self.get(benchmark_id)
            stored.state = state
            if approval is not None:
                stored.approvals.append(approval)
            if state is BenchmarkState.RUNNING:
                stored.started_at = now_iso()
            return stored

    def set_report(self, benchmark_id: str, report: BenchmarkReport) -> StoredBenchmark:
        artifact = self._artifacts.write_report(benchmark_id, report)
        with self._lock:
            stored = self.get(benchmark_id)
            stored.report = report
            stored.report_artifact_uri = artifact.uri
            stored.finished_at = now_iso()
            return stored


class RepositoryHub:
    """All repositories for one application instance (no global state)."""

    def __init__(self, artifacts: ArtifactStore) -> None:
        self.artifacts = artifacts
        self.maps = MapRepository()
        self.scenarios = ScenarioRepository()
        self.simulations = SimulationRepository()
        self.episodes = EpisodeRepository(artifacts)
        self.benchmarks = BenchmarkRepository(artifacts)
