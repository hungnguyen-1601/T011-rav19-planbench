"""Stored decision-layer objects and their in-memory repositories.

The decision layer was built as pure functions over files under
``artifacts/runs/``. This is what lets a run be *looked up* — which the
API needs before it can serve a result it did not just compute.

**A run is the record; a card is something a run sometimes produces.**
Revision ``0005`` modelled it the other way round, with ``card`` NOT
NULL, and the first MVP run disproved that assumption in a day: three
comparisons out of three produced no Decision Card, because a card needs
*two* candidates through all six gates and only one of four got there.
Each of those runs still carried a full gate table answering "who was
eliminated where, after how many runs" — the question HĐ-12 puts on a
card in the first place. So ``report`` is mandatory here and ``card`` is
optional, and reading it the other way is what puts pressure on every run
to be rankable.

Bodies stay as validated payloads rather than being shredded into fields:
``TaskProfile``, ``Candidate`` and the card are frozen Pydantic models
the decision layer already validates, and a second definition here would
drift from the first (§16).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Literal

from planbench_api.errors import DomainValidationError, InvalidStateError, NotFoundError
from planbench_api.repositories import new_id, now_iso

#: Which artifact a run produced. ``comparison`` covers a comparison that
#: could not be ranked *and* one that could — the card's presence is the
#: distinction, and ``decision_card`` names the case where one exists.
ArtifactKind = Literal["decision_card", "comparison", "measurement"]


@dataclass
class StoredTaskProfile:
    """One deployment as declared (HĐ-2), plus who filed it."""

    id: str
    environment: str
    owner_user_id: str | None
    created_at: str
    profile: dict[str, Any]


@dataclass
class StoredCandidate:
    """One registered candidate, keyed by its own content hash (HĐ-1.3)."""

    candidate_id: str
    type: str
    stack_label: str
    registered_by: str | None
    created_at: str
    spec: dict[str, Any]
    #: HĐ-1.6's declaration with its evidence log. ``None`` means the
    #: candidate declined to declare — which the objectives layer charges
    #: it for, rather than the schema pretending it did.
    tuning: dict[str, Any] | None = None


@dataclass
class StoredDecisionRun:
    """One evaluation run: always evidence, sometimes a recommendation."""

    id: str
    task_profile_id: str
    artifact_kind: ArtifactKind
    contracts_version: str
    created_at: str
    created_by: str | None
    report: dict[str, Any]
    experiment_scope: str | None = None
    card: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    recommended_candidate_id: str | None = None
    status: str | None = None
    run_uri: str | None = None
    run_checksum: str | None = None

    @property
    def ranked(self) -> bool:
        """Did this run support a recommendation at all?"""
        return self.card is not None


class TaskProfileRepository:
    """Deployments, keyed by the id their own author chose.

    The id is **not** a surrogate: profiles are referenced by
    ``task_profile_id`` inside every ``episode_context_id`` hash (HĐ-3.1),
    so the name in the YAML is the identity and generating another one
    here would create a second.
    """

    def __init__(self) -> None:
        self._items: dict[str, StoredTaskProfile] = {}
        self._lock = threading.Lock()

    def create(
        self, profile: dict[str, Any], *, owner_user_id: str | None = None
    ) -> StoredTaskProfile:
        """Store a profile, refusing to redefine one that exists.

        **Re-filing the same id with different content is a conflict, not
        an update**, and this is the trap it closes. ``episode_context_id``
        hashes ``(task_profile_id, mission_id, environment_variant,
        seed)`` and HĐ-3.1 freezes that payload — the traffic and the
        sensor-noise amplitudes are *not* in it. So a profile edited in
        place under the same id produces contexts that hash identically
        to the old ones, and every stored run pointing at that id
        silently starts describing a world that no longer exists. On disk
        the rule is kept by naming discipline (``open_hall_v1`` versus
        ``v2``); here it is an error.
        """
        profile_id = str(profile.get("id", "")).strip()
        if not profile_id:
            raise DomainValidationError("a task profile must declare an id (HĐ-2)")
        with self._lock:
            existing = self._items.get(profile_id)
            if existing is not None:
                if existing.profile != profile:
                    raise InvalidStateError(
                        f"task profile {profile_id!r} already exists with different content. "
                        "episode_context_id does not hash the environment (HĐ-3.1), so "
                        "reusing an id for a changed deployment would make stored runs "
                        "describe a world that no longer exists. Give the new deployment a "
                        "new id, the way open_hall_v1 and open_hall_v2 do"
                    )
                return existing
            stored = StoredTaskProfile(
                id=profile_id,
                environment=str(profile.get("environment", {}).get("map", "")),
                owner_user_id=owner_user_id,
                created_at=now_iso(),
                profile=profile,
            )
            self._items[profile_id] = stored
            return stored

    def get(self, profile_id: str) -> StoredTaskProfile:
        with self._lock:
            stored = self._items.get(profile_id)
        if stored is None:
            raise NotFoundError("task profile", profile_id)
        return stored

    def list(self) -> list[StoredTaskProfile]:
        with self._lock:
            return list(self._items.values())


class CandidateRepository:
    """Candidates, keyed by ``candidate_id`` (HĐ-1.3).

    Registering the same candidate twice is idempotent rather than an
    error: the id *is* the content hash, so a second registration of the
    same configuration carries no new information. Two different specs
    cannot collide under one id without breaking sha256.
    """

    def __init__(self) -> None:
        self._items: dict[str, StoredCandidate] = {}
        self._lock = threading.Lock()

    def create(
        self,
        spec: dict[str, Any],
        *,
        candidate_id: str,
        stack_label: str,
        registered_by: str | None = None,
        tuning: dict[str, Any] | None = None,
    ) -> StoredCandidate:
        with self._lock:
            existing = self._items.get(candidate_id)
            if existing is not None:
                return existing
            stored = StoredCandidate(
                candidate_id=candidate_id,
                type=str(spec.get("type", "modular")),
                stack_label=stack_label,
                registered_by=registered_by,
                created_at=now_iso(),
                spec=spec,
                tuning=tuning,
            )
            self._items[candidate_id] = stored
            return stored

    def get(self, candidate_id: str) -> StoredCandidate:
        with self._lock:
            stored = self._items.get(candidate_id)
        if stored is None:
            raise NotFoundError("candidate", candidate_id)
        return stored

    def list(self) -> list[StoredCandidate]:
        with self._lock:
            return list(self._items.values())


class DecisionRunRepository:
    """Runs. Every one has evidence; some also have a recommendation."""

    def __init__(self) -> None:
        self._items: dict[str, StoredDecisionRun] = {}
        self._lock = threading.Lock()

    def create(self, run: StoredDecisionRun) -> StoredDecisionRun:
        with self._lock:
            self._items[run.id] = run
            return run

    def get(self, run_id: str) -> StoredDecisionRun:
        with self._lock:
            stored = self._items.get(run_id)
        if stored is None:
            raise NotFoundError("decision run", run_id)
        return stored

    def list(
        self, *, task_profile_id: str | None = None, ranked: bool | None = None
    ) -> list[StoredDecisionRun]:
        """Filterable because "show me the runs that could not be ranked"
        is a day-one question, and an answer nobody can query is an
        answer people stop asking for."""
        with self._lock:
            rows = list(self._items.values())
        if task_profile_id is not None:
            rows = [row for row in rows if row.task_profile_id == task_profile_id]
        if ranked is not None:
            rows = [row for row in rows if row.ranked is ranked]
        return rows


@dataclass
class DecisionRepositories:
    """The three repositories, so a hub gains them in one line."""

    task_profiles: TaskProfileRepository = field(default_factory=TaskProfileRepository)
    candidates: CandidateRepository = field(default_factory=CandidateRepository)
    decision_runs: DecisionRunRepository = field(default_factory=DecisionRunRepository)


def new_run_id() -> str:
    return new_id()
