"""SQL implementations of the repository ports.

They return the same ``Stored*`` dataclasses as the in-memory backend,
so every service, router and test above this layer is unchanged by the
switch. That is the whole design goal: swapping storage must not be
visible from the outside.

Two things worth knowing when reading this file:

**Episodes are rehydrated from the artifact store.** A row keeps the
metadata and the artifact URI (decision D15); ``StoredEpisode.run`` is
reconstructed by reading that artifact. The in-memory backend keeps the
object alive instead, so a benchmark whose artifacts were deleted works
there and fails here — correctly, because the data really is gone.

**Every method is one transaction.** A failed write rolls back whole,
so a benchmark can never be left with a report but no state change.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from planbench_api.approval import ApprovalRecord, BenchmarkState
from planbench_api.artifacts import ArtifactStore
from planbench_api.db.models import (
    ApprovalRow,
    BenchmarkRow,
    EpisodeRow,
    MapRow,
    ScenarioRow,
    SimulationRow,
)
from planbench_api.db.session import SessionFactory
from planbench_api.errors import NotFoundError
from planbench_api.repositories import (
    StoredBenchmark,
    StoredEpisode,
    StoredMap,
    StoredScenario,
    StoredSimulation,
    new_id,
    now_iso,
)
from planbench_benchmark import BenchmarkReport, BenchmarkSpec, RunRecord
from planbench_metrics import EpisodeMetrics
from planbench_planning import PlanResult
from planbench_schemas.episode import EpisodeResult
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import StackRun


class SqlMapRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(self, map_data: MapData) -> StoredMap:
        row = MapRow(
            id=new_id(),
            version=1,
            name=map_data.name,
            width=map_data.width,
            height=map_data.height,
            resolution=map_data.resolution,
            checksum=map_data.checksum(),
            created_at=now_iso(),
            payload=map_data.model_dump(mode="json"),
        )
        with self._sessions.begin() as session:
            session.add(row)
        return _to_map(row)

    def get(self, map_id: str) -> StoredMap:
        with self._sessions.begin() as session:
            return _to_map(_require(session, MapRow, map_id, "map"))

    def list(self) -> list[StoredMap]:
        with self._sessions.begin() as session:
            rows = session.scalars(select(MapRow).order_by(MapRow.created_at)).all()
            return [_to_map(row) for row in rows]

    def update(self, map_id: str, map_data: MapData) -> StoredMap:
        with self._sessions.begin() as session:
            row = _require(session, MapRow, map_id, "map")
            row.version += 1
            row.name = map_data.name
            row.width = map_data.width
            row.height = map_data.height
            row.resolution = map_data.resolution
            row.checksum = map_data.checksum()
            row.payload = map_data.model_dump(mode="json")
            session.flush()
            return _to_map(row)

    def delete(self, map_id: str) -> None:
        with self._sessions.begin() as session:
            session.delete(_require(session, MapRow, map_id, "map"))


class SqlScenarioRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(self, map_id: str, scenario: Scenario) -> StoredScenario:
        row = ScenarioRow(
            id=new_id(),
            version=1,
            map_id=map_id,
            name=scenario.name,
            created_at=now_iso(),
            payload=scenario.model_dump(mode="json"),
        )
        with self._sessions.begin() as session:
            session.add(row)
        return _to_scenario(row)

    def get(self, scenario_id: str) -> StoredScenario:
        with self._sessions.begin() as session:
            return _to_scenario(_require(session, ScenarioRow, scenario_id, "scenario"))

    def list(self) -> list[StoredScenario]:
        with self._sessions.begin() as session:
            rows = session.scalars(select(ScenarioRow).order_by(ScenarioRow.created_at)).all()
            return [_to_scenario(row) for row in rows]

    def update(self, scenario_id: str, map_id: str, scenario: Scenario) -> StoredScenario:
        with self._sessions.begin() as session:
            row = _require(session, ScenarioRow, scenario_id, "scenario")
            row.version += 1
            row.map_id = map_id
            row.name = scenario.name
            row.payload = scenario.model_dump(mode="json")
            session.flush()
            return _to_scenario(row)

    def delete(self, scenario_id: str) -> None:
        with self._sessions.begin() as session:
            session.delete(_require(session, ScenarioRow, scenario_id, "scenario"))


class SqlSimulationRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(
        self, map_id: str, scenario_id: str, algorithm: str, config: dict
    ) -> StoredSimulation:
        row = SimulationRow(
            id=new_id(),
            map_id=map_id,
            scenario_id=scenario_id,
            algorithm=algorithm,
            config=config,
            state="created",
            created_at=now_iso(),
            run=None,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return _to_simulation(row)

    def get(self, simulation_id: str) -> StoredSimulation:
        with self._sessions.begin() as session:
            return _to_simulation(_require(session, SimulationRow, simulation_id, "simulation"))

    def list(self) -> list[StoredSimulation]:
        with self._sessions.begin() as session:
            rows = session.scalars(select(SimulationRow).order_by(SimulationRow.created_at)).all()
            return [_to_simulation(row) for row in rows]

    def set_finished(self, simulation_id: str, run: StackRun) -> StoredSimulation:
        with self._sessions.begin() as session:
            row = _require(session, SimulationRow, simulation_id, "simulation")
            row.run = _dump_run(run)
            row.state = "finished"
            session.flush()
            return _to_simulation(row)


class SqlEpisodeRepository:
    """Metadata in SQL, trajectory in the artifact store."""

    def __init__(self, sessions: SessionFactory, artifacts: ArtifactStore) -> None:
        self._sessions = sessions
        self._artifacts = artifacts

    def create(
        self, benchmark_id: str, algorithm: str, seed: int, run: StackRun, record: RunRecord
    ) -> StoredEpisode:
        episode_id = new_id()
        # Write the artifact first: a row pointing at a missing artifact
        # is worse than an orphaned artifact, which is merely garbage.
        artifact = self._artifacts.write_episode(benchmark_id, episode_id, run)
        row = EpisodeRow(
            id=episode_id,
            benchmark_id=benchmark_id,
            algorithm=algorithm,
            seed=seed,
            episode_index=record.episode_index,
            status=record.status.value,
            created_at=now_iso(),
            record=record.model_dump(mode="json"),
            artifact_uri=artifact.uri,
            artifact_checksum=artifact.checksum,
            artifact_bytes=artifact.size_bytes,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return _to_episode(row, run)

    def get(self, episode_id: str) -> StoredEpisode:
        with self._sessions.begin() as session:
            row = _require(session, EpisodeRow, episode_id, "episode")
            return _to_episode(row, self._load_run(row))

    def list_for_benchmark(self, benchmark_id: str) -> list[StoredEpisode]:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(EpisodeRow)
                .where(EpisodeRow.benchmark_id == benchmark_id)
                .order_by(EpisodeRow.episode_index)
            ).all()
            return [_to_episode(row, self._load_run(row)) for row in rows]

    def _load_run(self, row: EpisodeRow) -> StackRun:
        try:
            payload = self._artifacts.read(row.artifact_uri)
        except (ValueError, OSError) as exc:
            # Say which episode and which URI: "file not found" alone
            # sends the reader hunting through the whole artifact tree.
            raise NotFoundError("episode artifact", f"{row.id} at {row.artifact_uri}") from exc
        return _load_run(payload)


class SqlBenchmarkRepository:
    def __init__(self, sessions: SessionFactory, artifacts: ArtifactStore) -> None:
        self._sessions = sessions
        self._artifacts = artifacts

    def create(
        self, spec: BenchmarkSpec, map_id: str, scenario_id: str, created_by: str
    ) -> StoredBenchmark:
        row = BenchmarkRow(
            id=new_id(),
            name=spec.name,
            map_id=map_id,
            scenario_id=scenario_id,
            created_by=created_by,
            state=BenchmarkState.DRAFT.value,
            created_at=now_iso(),
            spec=spec.model_dump(mode="json"),
        )
        with self._sessions.begin() as session:
            session.add(row)
            session.flush()
            return _to_benchmark(row)

    def get(self, benchmark_id: str) -> StoredBenchmark:
        with self._sessions.begin() as session:
            return _to_benchmark(_require(session, BenchmarkRow, benchmark_id, "benchmark"))

    def list(self) -> list[StoredBenchmark]:
        with self._sessions.begin() as session:
            rows = session.scalars(select(BenchmarkRow).order_by(BenchmarkRow.created_at)).all()
            return [_to_benchmark(row) for row in rows]

    def set_state(
        self, benchmark_id: str, state: BenchmarkState, approval: ApprovalRecord | None = None
    ) -> StoredBenchmark:
        with self._sessions.begin() as session:
            row = _require(session, BenchmarkRow, benchmark_id, "benchmark")
            row.state = state.value
            if approval is not None:
                row.approvals.append(
                    ApprovalRow(
                        sequence=len(row.approvals),
                        username=approval.user,
                        role=approval.role.value,
                        action=approval.action.value,
                        previous_state=approval.previous_state.value,
                        new_state=approval.new_state.value,
                        comment=approval.comment,
                        timestamp=approval.timestamp,
                    )
                )
            if state is BenchmarkState.RUNNING:
                row.started_at = now_iso()
            session.flush()
            return _to_benchmark(row)

    def set_report(self, benchmark_id: str, report: BenchmarkReport) -> StoredBenchmark:
        artifact = self._artifacts.write_report(benchmark_id, report)
        with self._sessions.begin() as session:
            row = _require(session, BenchmarkRow, benchmark_id, "benchmark")
            row.report = report.model_dump(mode="json")
            row.report_artifact_uri = artifact.uri
            row.conditions_checksum = report.fairness.conditions_checksum
            row.finished_at = now_iso()
            session.flush()
            return _to_benchmark(row)


class SqlRepositoryHub:
    """All SQL repositories for one application instance."""

    def __init__(self, sessions: SessionFactory, artifacts: ArtifactStore) -> None:
        self.sessions = sessions
        self.artifacts = artifacts
        self.maps = SqlMapRepository(sessions)
        self.scenarios = SqlScenarioRepository(sessions)
        self.simulations = SqlSimulationRepository(sessions)
        self.episodes = SqlEpisodeRepository(sessions, artifacts)
        self.benchmarks = SqlBenchmarkRepository(sessions, artifacts)


# -- row <-> domain ----------------------------------------------------


def _require(session: Session, model: type, key: str, label: str):
    row = session.get(model, key)
    if row is None:
        raise NotFoundError(label, key)
    return row


def _to_map(row: MapRow) -> StoredMap:
    return StoredMap(
        id=row.id,
        version=row.version,
        created_at=row.created_at,
        map_data=MapData.model_validate(row.payload),
    )


def _to_scenario(row: ScenarioRow) -> StoredScenario:
    return StoredScenario(
        id=row.id,
        version=row.version,
        map_id=row.map_id,
        created_at=row.created_at,
        scenario=Scenario.model_validate(row.payload),
    )


def _to_simulation(row: SimulationRow) -> StoredSimulation:
    return StoredSimulation(
        id=row.id,
        map_id=row.map_id,
        scenario_id=row.scenario_id,
        algorithm=row.algorithm,
        config=dict(row.config or {}),
        created_at=row.created_at,
        state=row.state,
        run=_load_run(row.run) if row.run else None,
    )


def _to_episode(row: EpisodeRow, run: StackRun) -> StoredEpisode:
    return StoredEpisode(
        id=row.id,
        benchmark_id=row.benchmark_id,
        algorithm=row.algorithm,
        seed=row.seed,
        created_at=row.created_at,
        record=RunRecord.model_validate(row.record),
        artifact_uri=row.artifact_uri,
        artifact_checksum=row.artifact_checksum,
        artifact_bytes=row.artifact_bytes,
        run=run,
    )


def _to_benchmark(row: BenchmarkRow) -> StoredBenchmark:
    return StoredBenchmark(
        id=row.id,
        spec=BenchmarkSpec.model_validate(row.spec),
        map_id=row.map_id,
        scenario_id=row.scenario_id,
        created_by=row.created_by,
        created_at=row.created_at,
        state=BenchmarkState(row.state),
        report=BenchmarkReport.model_validate(row.report) if row.report else None,
        approvals=[
            ApprovalRecord(
                benchmark_id=row.id,
                user=approval.username,
                role=approval.role,
                action=approval.action,
                previous_state=approval.previous_state,
                new_state=approval.new_state,
                comment=approval.comment,
                timestamp=approval.timestamp,
            )
            for approval in row.approvals
        ],
        started_at=row.started_at,
        finished_at=row.finished_at,
        report_artifact_uri=row.report_artifact_uri,
    )


def _dump_run(run: StackRun) -> dict:
    return {
        "algorithm": run.algorithm,
        "plan": run.plan.model_dump(mode="json"),
        "result": run.result.model_dump(mode="json"),
        "metrics": run.metrics.model_dump(mode="json"),
    }


def _load_run(payload: dict) -> StackRun:
    """Rebuild a StackRun from the shape ``write_episode`` stores."""
    return StackRun(
        algorithm=payload["algorithm"],
        plan=PlanResult.model_validate(payload["plan"]),
        result=EpisodeResult.model_validate(payload["result"]),
        metrics=EpisodeMetrics.model_validate(payload["metrics"]),
    )


__all__ = [
    "SqlBenchmarkRepository",
    "SqlEpisodeRepository",
    "SqlMapRepository",
    "SqlRepositoryHub",
    "SqlScenarioRepository",
    "SqlSimulationRepository",
]
