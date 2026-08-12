"""SQL repositories for the decision layer (HĐ-1, HĐ-2, HĐ-12/13).

Same contract as the in-memory versions in ``planbench_api.decisions``,
same returned objects — everything above this layer is unchanged by which
backend is configured.

The one rule worth restating at this level: **a run always has evidence
and sometimes has a card.** ``report`` is NOT NULL; ``card``,
``manifest``, ``recommended_candidate_id`` and ``status`` are not. See
revision ``0006`` for why the table was turned around.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planbench_api.db.models import (
    CandidateRow,
    DecisionRunReviewRow,
    DecisionRunRow,
    TaskProfileRow,
)
from planbench_api.db.session import SessionFactory
from planbench_api.decisions import (
    ReviewEvent,
    StoredCandidate,
    StoredDecisionRun,
    StoredTaskProfile,
)
from planbench_api.errors import InvalidStateError, NotFoundError
from planbench_api.repositories import now_iso


class SqlTaskProfileRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(
        self, profile: dict[str, Any], *, owner_user_id: str | None = None
    ) -> StoredTaskProfile:
        """Store a deployment, refusing to redefine one under its own id.

        The refusal is the point. ``episode_context_id`` hashes
        ``(task_profile_id, mission_id, environment_variant, seed)`` and
        HĐ-3.1 freezes that payload — the traffic and the sensor-noise
        amplitudes are **not** in it. Re-filing a changed deployment under
        the same id would therefore produce contexts hashing identically
        to the old ones, and every stored run pointing at that id would
        silently start describing a world that no longer exists, with
        nothing to warn anyone. On disk the rule is kept by naming
        discipline (``open_hall_v1`` versus ``v2``); here it is enforced.
        """
        profile_id = str(profile.get("id", "")).strip()
        with self._sessions.begin() as session:
            existing = session.get(TaskProfileRow, profile_id)
            if existing is not None:
                if existing.profile != profile:
                    raise InvalidStateError(
                        f"task profile {profile_id!r} already exists with different content. "
                        "episode_context_id does not hash the environment (HĐ-3.1), so "
                        "reusing an id for a changed deployment would make stored runs "
                        "describe a world that no longer exists. Give the new deployment a "
                        "new id, the way open_hall_v1 and open_hall_v2 do"
                    )
                return _to_profile(existing)
            row = TaskProfileRow(
                id=profile_id,
                environment=str(profile.get("environment", {}).get("map", "")),
                owner_user_id=owner_user_id,
                created_at=now_iso(),
                profile=profile,
            )
            session.add(row)
            session.flush()
            return _to_profile(row)

    def get(self, profile_id: str) -> StoredTaskProfile:
        with self._sessions.begin() as session:
            return _to_profile(_require(session, TaskProfileRow, profile_id, "task profile"))

    def list(self) -> list[StoredTaskProfile]:
        with self._sessions.begin() as session:
            rows = session.scalars(select(TaskProfileRow).order_by(TaskProfileRow.created_at)).all()
            return [_to_profile(row) for row in rows]


class SqlCandidateRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(
        self,
        spec: dict[str, Any],
        *,
        candidate_id: str,
        stack_label: str,
        registered_by: str | None = None,
        tuning: dict[str, Any] | None = None,
    ) -> StoredCandidate:
        """Idempotent, because ``candidate_id`` *is* the content hash.

        A second registration of the same configuration carries no new
        information (HĐ-1.3), and two different specs cannot land on one
        id without breaking sha256.
        """
        with self._sessions.begin() as session:
            existing = session.get(CandidateRow, candidate_id)
            if existing is not None:
                return _to_candidate(existing)
            row = CandidateRow(
                candidate_id=candidate_id,
                type=str(spec.get("type", "modular")),
                stack_label=stack_label,
                registered_by=registered_by,
                created_at=now_iso(),
                spec=spec,
                tuning=tuning,
            )
            session.add(row)
            session.flush()
            return _to_candidate(row)

    def get(self, candidate_id: str) -> StoredCandidate:
        with self._sessions.begin() as session:
            return _to_candidate(_require(session, CandidateRow, candidate_id, "candidate"))

    def list(self) -> list[StoredCandidate]:
        with self._sessions.begin() as session:
            rows = session.scalars(select(CandidateRow).order_by(CandidateRow.created_at)).all()
            return [_to_candidate(row) for row in rows]


class SqlDecisionRunRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def create(self, run: StoredDecisionRun) -> StoredDecisionRun:
        row = DecisionRunRow(
            id=run.id,
            task_profile_id=run.task_profile_id,
            artifact_kind=run.artifact_kind,
            experiment_scope=run.experiment_scope,
            contracts_version=run.contracts_version,
            created_at=run.created_at,
            created_by=run.created_by,
            report=run.report,
            card=run.card,
            manifest=run.manifest,
            recommended_candidate_id=run.recommended_candidate_id,
            status=run.status,
            run_uri=run.run_uri,
            run_checksum=run.run_checksum,
            review_state=run.review_state,
            reviewed_by=run.reviewed_by,
            reviewed_at=run.reviewed_at,
            # `StoredDecisionRun.__post_init__` has already promoted this
            # to `pending` when a card is present, so the column and the
            # dataclass cannot disagree about which runs are approvable.
            config_state=run.config_state,
            config_decided_by=run.config_decided_by,
            config_decided_at=run.config_decided_at,
        )
        with self._sessions.begin() as session:
            session.add(row)
            session.flush()
            return _to_run(row)

    def get(self, run_id: str) -> StoredDecisionRun:
        with self._sessions.begin() as session:
            return _to_run(_require(session, DecisionRunRow, run_id, "decision run"))

    def list(
        self, *, task_profile_id: str | None = None, ranked: bool | None = None
    ) -> list[StoredDecisionRun]:
        """Filtered in SQL, not in Python.

        "Show me the runs that could not be ranked" is a day-one
        question, and ``artifact_kind`` plus ``card IS NULL`` are indexed
        columns precisely so the answer is not a scan over JSON bodies.
        """
        statement = select(DecisionRunRow).order_by(DecisionRunRow.created_at)
        if task_profile_id is not None:
            statement = statement.where(DecisionRunRow.task_profile_id == task_profile_id)
        if ranked is True:
            statement = statement.where(DecisionRunRow.card.is_not(None))
        elif ranked is False:
            statement = statement.where(DecisionRunRow.card.is_(None))
        with self._sessions.begin() as session:
            return [_to_run(row) for row in session.scalars(statement).all()]

    # --- the two human acts (HĐ-14, phase 6.3) -------------------------
    #
    # The refusals live in the same order and with the same wording as
    # `decisions.DecisionRunRepository`. Two implementations of one rule
    # is the cost of having an in-memory hub and a SQL one; two *different*
    # rules would be the bug, so the tests run both through the same
    # assertions.

    def review(
        self, run_id: str, *, actor_user_id: str | None, username: str, comment: str
    ) -> StoredDecisionRun:
        with self._sessions.begin() as session:
            row = _require(session, DecisionRunRow, run_id, "decision run")
            if row.review_state == "reviewed":
                raise InvalidStateError(
                    f"decision run {run_id} was already reviewed by {row.reviewed_by} at "
                    f"{row.reviewed_at}. Re-reviewing would overwrite that name; the audit "
                    "trail is append-only (HĐ-14)"
                )
            previous = row.review_state
            row.review_state = "reviewed"
            row.reviewed_by = actor_user_id
            row.reviewed_at = now_iso()
            _append_event(
                session, run_id, "review", actor_user_id, username, previous, "reviewed", comment
            )
            session.flush()
            return _to_run(row)

    def decide_config(
        self,
        run_id: str,
        *,
        approve: bool,
        actor_user_id: str | None,
        username: str,
        comment: str,
    ) -> StoredDecisionRun:
        with self._sessions.begin() as session:
            row = _require(session, DecisionRunRow, run_id, "decision run")
            if row.config_state == "not_applicable":
                raise InvalidStateError(
                    f"decision run {run_id} produced no Decision Card, so it recommends no "
                    "configuration and there is nothing to approve. Its gate table is still a "
                    "result and can be reviewed — POST /decisions/{id}/review"
                )
            if row.config_state != "pending":
                raise InvalidStateError(
                    f"decision run {run_id} is already {row.config_state} (by "
                    f"{row.config_decided_by} at {row.config_decided_at}). That decision "
                    "stands; the way to change a recommendation is a new run, which leaves "
                    "both records in place"
                )
            if actor_user_id is not None and actor_user_id == row.created_by:
                raise InvalidStateError(
                    f"account {actor_user_id} started decision run {run_id} and cannot approve "
                    "its own recommendation (HĐ-14, separation of duties). Whoever chose the "
                    "candidates and the deployment is not an independent check on the result"
                )
            previous = row.config_state
            row.config_state = "approved" if approve else "rejected"
            row.config_decided_by = actor_user_id
            row.config_decided_at = now_iso()
            _append_event(
                session,
                run_id,
                "approve_config" if approve else "reject_config",
                actor_user_id,
                username,
                previous,
                row.config_state,
                comment,
            )
            session.flush()
            return _to_run(row)

    def events(self, run_id: str) -> list[ReviewEvent]:
        with self._sessions.begin() as session:
            _require(session, DecisionRunRow, run_id, "decision run")
            statement = (
                select(DecisionRunReviewRow)
                .where(DecisionRunReviewRow.run_id == run_id)
                .order_by(DecisionRunReviewRow.sequence)
            )
            return [_to_event(row) for row in session.scalars(statement).all()]


def _append_event(  # noqa: PLR0913 - one audit row, one argument each
    session: Session,
    run_id: str,
    action: str,
    actor_user_id: str | None,
    username: str,
    previous_state: str,
    new_state: str,
    comment: str,
) -> None:
    used = session.scalar(
        select(func.count())
        .select_from(DecisionRunReviewRow)
        .where(DecisionRunReviewRow.run_id == run_id)
    )
    session.add(
        DecisionRunReviewRow(
            run_id=run_id,
            sequence=(used or 0) + 1,
            action=action,
            actor_user_id=actor_user_id,
            username=username,
            previous_state=previous_state,
            new_state=new_state,
            comment=comment,
            created_at=now_iso(),
        )
    )


def _to_event(row: DecisionRunReviewRow) -> ReviewEvent:
    return ReviewEvent(
        run_id=row.run_id,
        sequence=row.sequence,
        action=row.action,  # type: ignore[arg-type]
        actor_user_id=row.actor_user_id,
        username=row.username,
        previous_state=row.previous_state,
        new_state=row.new_state,
        comment=row.comment,
        created_at=row.created_at,
    )


def _require(session: Session, model: type, key: str, label: str):  # type: ignore[no-untyped-def]
    row = session.get(model, key)
    if row is None:
        raise NotFoundError(label, key)
    return row


def _to_profile(row: TaskProfileRow) -> StoredTaskProfile:
    return StoredTaskProfile(
        id=row.id,
        environment=row.environment,
        owner_user_id=row.owner_user_id,
        created_at=row.created_at,
        profile=row.profile,
    )


def _to_candidate(row: CandidateRow) -> StoredCandidate:
    return StoredCandidate(
        candidate_id=row.candidate_id,
        type=row.type,
        stack_label=row.stack_label,
        registered_by=row.registered_by,
        created_at=row.created_at,
        spec=row.spec,
        tuning=row.tuning,
    )


def _to_run(row: DecisionRunRow) -> StoredDecisionRun:
    return StoredDecisionRun(
        id=row.id,
        task_profile_id=row.task_profile_id,
        artifact_kind=row.artifact_kind,  # type: ignore[arg-type]
        experiment_scope=row.experiment_scope,
        contracts_version=row.contracts_version,
        created_at=row.created_at,
        created_by=row.created_by,
        report=row.report,
        card=row.card,
        manifest=row.manifest,
        recommended_candidate_id=row.recommended_candidate_id,
        status=row.status,
        run_uri=row.run_uri,
        run_checksum=row.run_checksum,
        review_state=row.review_state,  # type: ignore[arg-type]
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        config_state=row.config_state,  # type: ignore[arg-type]
        config_decided_by=row.config_decided_by,
        config_decided_at=row.config_decided_at,
    )
