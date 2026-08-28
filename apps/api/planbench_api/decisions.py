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

#: Has a human looked at this run? Applies to **every** run, ranked or
#: not, and that is the whole point of it being separate from config
#: approval below. A comparison that eliminated four candidates is a real
#: result somebody has to read; leaving it with nowhere to record that
#: reading is how it becomes the forgotten artifact.
ReviewState = Literal["unreviewed", "reviewed"]

#: Is this run's recommendation the configuration we deploy?
#:
#: ``not_applicable`` is the value that does the work. A run with no card
#: recommends nothing, so there is nothing to approve — and expressing
#: that as a *state* rather than as a check inside the endpoint means the
#: refusal cannot be forgotten by a second caller. Approving an unranked
#: run would turn "this was measured" into "this was endorsed", which is
#: precisely the slide from evidence to recommendation the gates exist to
#: prevent (HĐ-7, HĐ-12).
ConfigState = Literal["not_applicable", "pending", "approved", "rejected"]

#: What a human did. Append-only vocabulary: nothing here undoes anything,
#: because an audit trail that can be rewound is not one (HĐ-14).
ReviewAction = Literal[
    "review",
    #: What ``review`` is called from the decision lane onwards. The old
    #: spelling stays valid so rows written before this still parse — an
    #: audit trail that cannot be read is not an audit trail.
    "acknowledge",
    "approve_config",
    "reject_config",
    "withdraw_config",
    #: A single-person deployment, where the same account created the run
    #: and signed it. Recorded under its own name so the trail never
    #: claims a second human looked.
    "self_approve_config",
    "self_reject_config",
    "algorithm_disabled_after_approval",
]


def same_deployment(stored: dict, incoming: dict) -> bool:
    """Do these two documents describe the same world?

    **Compared as deployments, not as dictionaries.** HĐ-2 has two legal
    encodings of a pose — the document form ``[x, y, theta]`` and the
    dumped form ``{"x": .., "y": .., "theta": ..}`` — and the store holds
    both, because the API dumps a validated model while
    ``scripts/import_runs.py`` used to file the YAML as written. Comparing
    the raw dicts therefore called one deployment two, and re-filing an
    unchanged profile was refused with "already exists with different
    content" while nothing about the world had changed.

    Validating both sides also makes the comparison indifferent to key
    order, to ``1`` against ``1.0``, and to an omitted field that equals
    its default — none of which is a different world either.

    A document that will not validate falls back to dict equality, which
    refuses unless the bytes match. That is the safe direction: the guard
    exists to stop one id meaning two worlds, so an unanswerable question
    must not resolve to "same".
    """
    from planbench_schemas.task_profile import TaskProfile

    try:
        return TaskProfile.model_validate(stored) == TaskProfile.model_validate(incoming)
    except Exception:
        return stored == incoming


@dataclass
class StoredTaskProfile:
    """One deployment as declared (HĐ-2), plus who filed it."""

    id: str
    environment: str
    owner_user_id: str | None
    created_at: str
    profile: dict[str, Any]
    #: A deployment a reviewer validates imported algorithms against.
    #: Refuses to be edited or deleted, which ``owner_user_id is None``
    #: cannot express — that already means "filed before accounts", which
    #: is shared rather than fixed. A validation result is only
    #: comparable across bundles if the thing they ran on did not move
    #: between them.
    is_reference: bool = False
    archived_at: str | None = None


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
    #: What this run is for. A validation run carries no verdict: it is
    #: a reviewer watching an unpublished algorithm behave, and letting
    #: one be approved would put a conclusion on evidence gathered
    #: precisely because nobody had vouched for the code yet.
    purpose: str = "production"
    #: The code each candidate resolved to, in request order. Empty for
    #: runs stored before this was recorded — see the backfill script.
    candidates: list[dict[str, Any]] = field(default_factory=list)
    review_state: ReviewState = "unreviewed"
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    #: Defaulted here rather than passed in, so a caller that forgets it
    #: gets the safe value. :meth:`__post_init__` corrects it upward for
    #: ranked runs; there is no path that makes an unranked run approvable.
    config_state: ConfigState = "not_applicable"
    config_decided_by: str | None = None
    config_decided_at: str | None = None

    def __post_init__(self) -> None:
        if self.card is not None and self.config_state == "not_applicable":
            self.config_state = "pending"

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
                if not same_deployment(existing.profile, profile):
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

    def delete(self, profile_id: str) -> None:
        """Remove a deployment. Whether that is allowed is decided above.

        The repository does not consult the runs: the rule is "a run is a
        statement about a deployment", which is a fact about the two
        stores together and belongs to the service that can see both. A
        repository enforcing it would put the same rule in two places, and
        the SQL one already has it as a foreign key.
        """
        with self._lock:
            self._items.pop(profile_id, None)

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


def _decision_action(approve: bool, alone: bool) -> str:
    """What to call this in the trail.

    ``self_*`` when one account both created the run and signed it. The
    outcome is identical; the record is not, and a reader has to be able
    to tell a second pair of eyes from the absence of one.
    """
    if alone:
        return "self_approve_config" if approve else "self_reject_config"
    return "approve_config" if approve else "reject_config"


@dataclass
class ReviewEvent:
    """One human act on one run. Append-only (HĐ-14).

    Carries both states rather than just the new one, because "approved"
    on its own does not say what it replaced, and a trail that cannot say
    what changed is a list of timestamps.
    """

    run_id: str
    sequence: int
    action: ReviewAction
    actor_user_id: str | None
    username: str
    previous_state: str
    new_state: str
    comment: str
    created_at: str


class DecisionRunRepository:
    """Runs. Every one has evidence; some also have a recommendation."""

    def __init__(self) -> None:
        self._items: dict[str, StoredDecisionRun] = {}
        self._events: dict[str, list[ReviewEvent]] = {}
        self._lock = threading.Lock()

    def delete_for_profile(self, task_profile_id: str) -> int:
        """Delete every run filed against one deployment; return how many."""
        with self._lock:
            doomed = [
                run_id
                for run_id, run in self._items.items()
                if run.task_profile_id == task_profile_id
            ]
            for run_id in doomed:
                del self._items[run_id]
            return len(doomed)

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

    # --- the two human acts (HĐ-14, phase 6.3) -------------------------

    def review(
        self, run_id: str, *, actor_user_id: str | None, username: str, comment: str
    ) -> StoredDecisionRun:
        """Record that somebody read this run's evidence.

        Allowed on **every** run, including one that could not be ranked
        and one whose config was already rejected. Reviewing is a claim
        about having looked, not about endorsing anything, so nothing
        about the run's outcome can disqualify it.

        Reviewing twice is refused rather than silently re-stamped: the
        second reviewer would overwrite the first one's name, and the
        audit trail would then disagree with the row it describes.
        """
        with self._lock:
            run = self._require(run_id)
            if run.review_state == "reviewed":
                raise InvalidStateError(
                    f"decision run {run_id} was already reviewed by {run.reviewed_by} at "
                    f"{run.reviewed_at}. Re-reviewing would overwrite that name; the audit "
                    "trail is append-only (HĐ-14)"
                )
            previous = run.review_state
            run.review_state = "reviewed"
            run.reviewed_by = actor_user_id
            run.reviewed_at = now_iso()
            self._append(run_id, "review", actor_user_id, username, previous, "reviewed", comment)
            return run

    def decide_config(
        self,
        run_id: str,
        *,
        approve: bool,
        actor_user_id: str | None,
        username: str,
        comment: str,
        relaxed: bool = False,
    ) -> StoredDecisionRun:
        """Approve or reject this run's recommendation as a configuration.

        Three refusals, and each closes a different hole:

        **No card, nothing to approve.** ``config_state`` is
        ``not_applicable`` on an unranked run, and this reads that state
        rather than re-deriving it — the check and the stored value cannot
        drift apart if there is only one of them. Without this, approving
        a run that eliminated every candidate would produce an
        ``approved_config.yaml`` naming nobody.

        **Nobody approves their own run.** Separation of duties (HĐ-14).
        The person who launched the comparison chose its candidates, its
        deployment and its episode count; letting them also sign off the
        result removes the only independent step in the chain.

        **Decided is decided.** ``approved`` and ``rejected`` are both
        terminal. Re-deciding would let a rejection be quietly flipped
        after the fact, and the legitimate answer to "we were wrong" is a
        new run — which is cheap, dated, and leaves both records standing.
        """
        with self._lock:
            run = self._require(run_id)
            if run.config_state == "not_applicable":
                raise InvalidStateError(
                    f"decision run {run_id} produced no Decision Card, so it recommends no "
                    "configuration and there is nothing to approve. Its gate table is still a "
                    "result and can be reviewed — POST /decisions/{id}/review"
                )
            if run.config_state != "pending":
                raise InvalidStateError(
                    f"decision run {run_id} is already {run.config_state} (by "
                    f"{run.config_decided_by} at {run.config_decided_at}). That decision "
                    "stands; the way to change a recommendation is a new run, which leaves "
                    "both records in place"
                )
            own_run = actor_user_id is not None and actor_user_id == run.created_by
            if own_run and not relaxed:
                raise InvalidStateError(
                    f"account {actor_user_id} started decision run {run_id} and cannot approve "
                    "its own recommendation (HĐ-14, separation of duties). Whoever chose the "
                    "candidates and the deployment is not an independent check on the result"
                )
            previous = run.config_state
            run.config_state = "approved" if approve else "rejected"
            run.config_decided_by = actor_user_id
            run.config_decided_at = now_iso()
            self._append(
                run_id,
                _decision_action(approve, own_run and relaxed),
                actor_user_id,
                username,
                previous,
                run.config_state,
                comment,
            )
            return run

    def withdraw_config(
        self,
        run_id: str,
        *,
        actor_user_id: str | None,
        username: str,
        comment: str,
    ) -> StoredDecisionRun:
        """Take an approval back, so the run can be re-decided or deleted.

        **This does not erase the approval; it adds to it.** The journal
        keeps the approve event and gains a withdraw event beside it, with
        the name of whoever took it back and their reason. That is what
        keeps HĐ-14 intact: the record of a signed decision survives, and
        so does the record of it being unsigned. An approval that could be
        silently unwound would be an approval nobody could rely on.

        **Why this exists at all**, given that "decided is decided" is
        deliberate. Two things needed a door: deleting a deployment
        refuses while any of its runs is approved — and a message telling
        somebody to withdraw an approval they cannot withdraw is a wall
        with a sign on it — and a configuration signed off in error had no
        exit that was not a new run measuring nothing new.

        The state returns to ``pending`` rather than to ``rejected``:
        withdrawing says *"this is undecided again"*, not *"we decided
        against it"*, and writing the second when somebody meant the first
        would put a verdict in the record nobody reached.
        """
        with self._lock:
            run = self._require(run_id)
            if run.config_state != "approved":
                raise InvalidStateError(
                    f"decision run {run_id} is {run.config_state}, not approved, so there is "
                    "no approval to withdraw"
                )
            previous = run.config_state
            run.config_state = "pending"
            run.config_decided_by = None
            run.config_decided_at = None
            self._append(
                run_id, "withdraw_config", actor_user_id, username, previous, "pending", comment
            )
            return run

    def events(self, run_id: str) -> list[ReviewEvent]:
        with self._lock:
            self._require(run_id)
            return list(self._events.get(run_id, []))

    def _require(self, run_id: str) -> StoredDecisionRun:
        """Caller already holds the lock."""
        stored = self._items.get(run_id)
        if stored is None:
            raise NotFoundError("decision run", run_id)
        return stored

    def _append(  # noqa: PLR0913 - one audit row, one argument each
        self,
        run_id: str,
        action: ReviewAction,
        actor_user_id: str | None,
        username: str,
        previous_state: str,
        new_state: str,
        comment: str,
    ) -> None:
        """Caller already holds the lock."""
        trail = self._events.setdefault(run_id, [])
        trail.append(
            ReviewEvent(
                run_id=run_id,
                # Explicit, because two events can share a timestamp at
                # whatever resolution the clock happens to have — the same
                # reason `approvals.sequence` exists for benchmarks.
                sequence=len(trail) + 1,
                action=action,
                actor_user_id=actor_user_id,
                username=username,
                previous_state=previous_state,
                new_state=new_state,
                comment=comment,
                created_at=now_iso(),
            )
        )


@dataclass
class DecisionRepositories:
    """The three repositories, so a hub gains them in one line."""

    task_profiles: TaskProfileRepository = field(default_factory=TaskProfileRepository)
    candidates: CandidateRepository = field(default_factory=CandidateRepository)
    decision_runs: DecisionRunRepository = field(default_factory=DecisionRunRepository)


def new_run_id() -> str:
    return new_id()
