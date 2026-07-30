"""The repository contract, independent of where the data actually lives.

Until M10 the only implementation was in-memory. Adding PostgreSQL
without writing these down would have meant the SQL classes "matching"
the dict-backed ones by luck: one renamed argument and the API would
break at runtime in whichever deployment happened to use the other
backend.

These Protocols are structural, so neither implementation has to inherit
anything — the in-memory classes already satisfied them before this file
existed. What the file adds is a single place that says what a
repository *is*, and a type error when an implementation drifts.

Storage split (decision D15) applies to both backends: large payloads —
episode trajectories, benchmark reports — go to the artifact store, and
the repository keeps metadata plus the URI. So a SQL row is small, and
replay reads the artifact rather than a blob column.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from planbench_api.approval import ApprovalRecord, BenchmarkState
from planbench_api.repositories import (
    StoredBenchmark,
    StoredEpisode,
    StoredMap,
    StoredScenario,
    StoredSimulation,
)
from planbench_benchmark import BenchmarkReport, BenchmarkSpec, RunRecord
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import StackRun


@runtime_checkable
class MapRepositoryPort(Protocol):
    def create(self, map_data: MapData) -> StoredMap: ...
    def get(self, map_id: str) -> StoredMap: ...
    def list(self) -> list[StoredMap]: ...
    def update(self, map_id: str, map_data: MapData) -> StoredMap: ...
    def delete(self, map_id: str) -> None: ...


@runtime_checkable
class ScenarioRepositoryPort(Protocol):
    def create(self, map_id: str, scenario: Scenario) -> StoredScenario: ...
    def get(self, scenario_id: str) -> StoredScenario: ...
    def list(self) -> list[StoredScenario]: ...
    def update(self, scenario_id: str, map_id: str, scenario: Scenario) -> StoredScenario: ...
    def delete(self, scenario_id: str) -> None: ...


@runtime_checkable
class SimulationRepositoryPort(Protocol):
    def create(
        self, map_id: str, scenario_id: str, algorithm: str, config: dict
    ) -> StoredSimulation: ...
    def get(self, simulation_id: str) -> StoredSimulation: ...
    def list(self) -> list[StoredSimulation]: ...
    def set_finished(self, simulation_id: str, run: StackRun) -> StoredSimulation: ...


@runtime_checkable
class EpisodeRepositoryPort(Protocol):
    def create(
        self, benchmark_id: str, algorithm: str, seed: int, run: StackRun, record: RunRecord
    ) -> StoredEpisode: ...
    def get(self, episode_id: str) -> StoredEpisode: ...
    def list_for_benchmark(self, benchmark_id: str) -> list[StoredEpisode]: ...


@runtime_checkable
class BenchmarkRepositoryPort(Protocol):
    def create(
        self, spec: BenchmarkSpec, map_id: str, scenario_id: str, created_by: str
    ) -> StoredBenchmark: ...
    def get(self, benchmark_id: str) -> StoredBenchmark: ...
    def list(self) -> list[StoredBenchmark]: ...
    def set_state(
        self, benchmark_id: str, state: BenchmarkState, approval: ApprovalRecord | None = None
    ) -> StoredBenchmark: ...
    def set_report(self, benchmark_id: str, report: BenchmarkReport) -> StoredBenchmark: ...


@runtime_checkable
class RepositoryHubPort(Protocol):
    """What the application needs from a storage backend."""

    maps: MapRepositoryPort
    scenarios: ScenarioRepositoryPort
    simulations: SimulationRepositoryPort
    episodes: EpisodeRepositoryPort
    benchmarks: BenchmarkRepositoryPort


__all__ = [
    "BenchmarkRepositoryPort",
    "EpisodeRepositoryPort",
    "MapRepositoryPort",
    "RepositoryHubPort",
    "ScenarioRepositoryPort",
    "SimulationRepositoryPort",
]
