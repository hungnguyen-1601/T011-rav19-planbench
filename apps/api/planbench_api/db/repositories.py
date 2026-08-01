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

from planbench_api.accounts import (
    AccountLinkError,
    AuthProvider,
    NicknameError,
    OAuthAccount,
    StoredUser,
    User,
    UserRole,
    normalise_nickname,
    validate_nickname,
)
from planbench_api.approval import ApprovalRecord, BenchmarkState
from planbench_api.artifacts import ArtifactStore
from planbench_api.db.models import (
    ApprovalRow,
    BenchmarkRow,
    EpisodeRow,
    MapRow,
    OAuthAccountRow,
    ReviewRequestRow,
    ScenarioRow,
    SimulationRow,
    UserRow,
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
from planbench_api.review import ReviewRequest, ReviewStage, ReviewStatus
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
        self,
        spec: BenchmarkSpec,
        map_id: str,
        scenario_id: str,
        created_by: str,
        owner_user_id: str = "",
    ) -> StoredBenchmark:
        row = BenchmarkRow(
            id=new_id(),
            name=spec.name,
            map_id=map_id,
            scenario_id=scenario_id,
            created_by=created_by,
            owner_user_id=owner_user_id or None,
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
                        user_id=approval.user_id or None,
                        review_request_id=approval.review_request_id,
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


class SqlUserRepository:
    """Accounts and their linked provider identities.

    Uniqueness is enforced twice on purpose: a lookup first, so the
    caller gets a readable message, and a database constraint, so two
    simultaneous requests cannot both pass the lookup and both insert.
    Only the constraint is a guarantee; only the lookup is a good error.
    """

    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(
        self,
        *,
        nickname: str = "",
        email: str = "",
        display_name: str = "",
        avatar_url: str = "",
        is_admin: bool = False,
        role: UserRole = UserRole.ENGINEER,
        password_hash: str | None = None,
    ) -> User:
        key = None
        if nickname:
            nickname = validate_nickname(nickname)
            key = normalise_nickname(nickname)
        stamp = now_iso()
        row = UserRow(
            id=new_id(),
            nickname=nickname,
            nickname_key=key,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            is_admin=is_admin,
            role=role.value,
            password_hash=password_hash,
            created_at=stamp,
            updated_at=stamp,
        )
        with self._sessions.begin() as session:
            if key is not None and _nickname_owner(session, key) is not None:
                raise NicknameError(f"nickname {nickname!r} is already taken")
            session.add(row)
            session.flush()
            return _to_user(row)

    def get(self, user_id: str) -> User:
        with self._sessions.begin() as session:
            return _to_user(_require(session, UserRow, user_id, "user"))

    def get_stored(self, user_id: str) -> StoredUser:
        with self._sessions.begin() as session:
            row = _require(session, UserRow, user_id, "user")
            return StoredUser(
                user=_to_user(row),
                nickname_key=row.nickname_key or "",
                password_hash=row.password_hash,
            )

    def find_by_nickname(self, nickname: str) -> User | None:
        key = normalise_nickname(nickname)
        if not key:
            return None
        with self._sessions.begin() as session:
            row = _nickname_owner(session, key)
            return _to_user(row) if row is not None else None

    def search_by_nickname(self, prefix: str, limit: int = 10) -> list[User]:
        needle = normalise_nickname(prefix)
        if not needle:
            return []
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(UserRow)
                # Prefix match only: a substring search would let anyone
                # enumerate the member list from a single character.
                .where(UserRow.nickname_key.startswith(needle))
                .order_by(UserRow.nickname_key)
                .limit(limit)
            ).all()
            return [_to_user(row) for row in rows]

    def set_nickname(self, user_id: str, nickname: str) -> User:
        cleaned = validate_nickname(nickname)
        key = normalise_nickname(cleaned)
        with self._sessions.begin() as session:
            row = _require(session, UserRow, user_id, "user")
            owner = _nickname_owner(session, key)
            if owner is not None and owner.id != user_id:
                raise NicknameError(f"nickname {cleaned!r} is already taken")
            row.nickname = cleaned
            row.nickname_key = key
            row.updated_at = now_iso()
            session.flush()
            return _to_user(row)

    def update_profile(
        self,
        user_id: str,
        *,
        email: str | None = None,
        display_name: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        with self._sessions.begin() as session:
            row = _require(session, UserRow, user_id, "user")
            if email is not None:
                row.email = email
            if display_name is not None:
                row.display_name = display_name
            if avatar_url is not None:
                row.avatar_url = avatar_url
            row.updated_at = now_iso()
            session.flush()
            return _to_user(row)

    def set_admin(self, user_id: str, is_admin: bool) -> User:
        with self._sessions.begin() as session:
            row = _require(session, UserRow, user_id, "user")
            row.is_admin = is_admin
            row.updated_at = now_iso()
            session.flush()
            return _to_user(row)

    def set_role(self, user_id: str, role: UserRole) -> User:
        with self._sessions.begin() as session:
            row = _require(session, UserRow, user_id, "user")
            row.role = role.value
            row.updated_at = now_iso()
            session.flush()
            return _to_user(row)

    def list(self) -> list[User]:
        with self._sessions.begin() as session:
            rows = session.scalars(select(UserRow).order_by(UserRow.created_at)).all()
            return [_to_user(row) for row in rows]

    def link_oauth(
        self,
        *,
        user_id: str,
        provider: AuthProvider,
        provider_account_id: str,
        provider_email: str = "",
    ) -> OAuthAccount:
        stamp = now_iso()
        with self._sessions.begin() as session:
            _require(session, UserRow, user_id, "user")
            row = session.scalars(
                select(OAuthAccountRow).where(
                    OAuthAccountRow.provider == provider.value,
                    OAuthAccountRow.provider_account_id == provider_account_id,
                )
            ).first()
            if row is not None and row.user_id != user_id:
                raise AccountLinkError(
                    f"that {provider.value} account is already linked to another PlanBench account"
                )
            if row is None:
                row = OAuthAccountRow(
                    id=new_id(),
                    user_id=user_id,
                    provider=provider.value,
                    provider_account_id=provider_account_id,
                    provider_email=provider_email,
                    created_at=stamp,
                    updated_at=stamp,
                )
                session.add(row)
            else:
                row.provider_email = provider_email
                row.updated_at = stamp
            session.flush()
            return _to_oauth(row)

    def find_oauth(self, provider: AuthProvider, provider_account_id: str) -> OAuthAccount | None:
        with self._sessions.begin() as session:
            row = session.scalars(
                select(OAuthAccountRow).where(
                    OAuthAccountRow.provider == provider.value,
                    OAuthAccountRow.provider_account_id == provider_account_id,
                )
            ).first()
            return _to_oauth(row) if row is not None else None

    def list_oauth(self, user_id: str) -> list[OAuthAccount]:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(OAuthAccountRow)
                .where(OAuthAccountRow.user_id == user_id)
                .order_by(OAuthAccountRow.created_at)
            ).all()
            return [_to_oauth(row) for row in rows]


class SqlReviewRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(self, request: ReviewRequest) -> ReviewRequest:
        row = ReviewRequestRow(
            id=request.id or new_id(),
            benchmark_id=request.benchmark_id,
            stage=request.stage.value,
            requested_by_user_id=request.requested_by_user_id,
            reviewer_user_id=request.reviewer_user_id,
            status=request.status.value,
            request_comment=request.request_comment,
            review_comment=request.review_comment,
            created_at=request.created_at or now_iso(),
            reviewed_at=request.reviewed_at,
            cancelled_at=request.cancelled_at,
        )
        with self._sessions.begin() as session:
            session.add(row)
            session.flush()
            return _to_review(row)

    def get(self, request_id: str) -> ReviewRequest:
        with self._sessions.begin() as session:
            return _to_review(_require(session, ReviewRequestRow, request_id, "review request"))

    def save(self, request: ReviewRequest) -> ReviewRequest:
        with self._sessions.begin() as session:
            row = _require(session, ReviewRequestRow, request.id, "review request")
            row.status = request.status.value
            row.request_comment = request.request_comment
            row.review_comment = request.review_comment
            row.reviewed_at = request.reviewed_at
            row.cancelled_at = request.cancelled_at
            session.flush()
            return _to_review(row)

    def list_for_benchmark(self, benchmark_id: str) -> list[ReviewRequest]:
        return self._query(ReviewRequestRow.benchmark_id == benchmark_id)

    def list_for_reviewer(
        self, reviewer_user_id: str, status: ReviewStatus | None = None
    ) -> list[ReviewRequest]:
        clauses = [ReviewRequestRow.reviewer_user_id == reviewer_user_id]
        if status is not None:
            clauses.append(ReviewRequestRow.status == status.value)
        return self._query(*clauses)

    def list_requested_by(self, user_id: str) -> list[ReviewRequest]:
        return self._query(ReviewRequestRow.requested_by_user_id == user_id)

    def _query(self, *clauses) -> list[ReviewRequest]:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(ReviewRequestRow)
                .where(*clauses)
                .order_by(ReviewRequestRow.created_at.desc())
            ).all()
            return [_to_review(row) for row in rows]


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
        self.users = SqlUserRepository(sessions)
        self.reviews = SqlReviewRepository(sessions)


# -- row <-> domain ----------------------------------------------------


def _require(session: Session, model: type, key: str, label: str):
    row = session.get(model, key)
    if row is None:
        raise NotFoundError(label, key)
    return row


def _nickname_owner(session: Session, key: str) -> UserRow | None:
    return session.scalars(select(UserRow).where(UserRow.nickname_key == key)).first()


def _to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        nickname=row.nickname or "",
        email=row.email or "",
        display_name=row.display_name or "",
        avatar_url=row.avatar_url or "",
        is_admin=bool(row.is_admin),
        role=UserRole(row.role) if row.role else UserRole.ENGINEER,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_oauth(row: OAuthAccountRow) -> OAuthAccount:
    return OAuthAccount(
        id=row.id,
        user_id=row.user_id,
        provider=AuthProvider(row.provider),
        provider_account_id=row.provider_account_id,
        provider_email=row.provider_email or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_review(row: ReviewRequestRow) -> ReviewRequest:
    return ReviewRequest(
        id=row.id,
        benchmark_id=row.benchmark_id,
        stage=ReviewStage(row.stage),
        requested_by_user_id=row.requested_by_user_id,
        reviewer_user_id=row.reviewer_user_id,
        status=ReviewStatus(row.status),
        request_comment=row.request_comment or "",
        review_comment=row.review_comment or "",
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
        cancelled_at=row.cancelled_at,
    )


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
        owner_user_id=row.owner_user_id or "",
        state=BenchmarkState(row.state),
        report=BenchmarkReport.model_validate(row.report) if row.report else None,
        approvals=[
            ApprovalRecord(
                benchmark_id=row.id,
                user=approval.username,
                user_id=approval.user_id or "",
                review_request_id=approval.review_request_id,
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
    "SqlReviewRepository",
    "SqlUserRepository",
    "SqlEpisodeRepository",
    "SqlMapRepository",
    "SqlRepositoryHub",
    "SqlScenarioRepository",
    "SqlSimulationRepository",
]
