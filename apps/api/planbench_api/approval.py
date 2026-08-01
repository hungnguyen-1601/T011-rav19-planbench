"""Benchmark lifecycle: states, transitions and the audit trail.

    DRAFT ──submit──> PENDING_APPROVAL ──approve──> APPROVED ──run──> RUNNING ──complete──> PENDING_REVIEW
                            │                                                                      │
                            └──reject──> DRAFT                                        accept_result│└──reject_result──┐
                                                                                                     v                  v
                                                                                                 ACCEPTED           REJECTED

A prior revision let the owner drive every step alone, including
``self_approve`` straight from DRAFT — authority came from ownership,
not role, and review was opt-in. That traded away the one thing this
gate exists to guarantee: a benchmark result was seen by someone other
than the person who produced it. ``SELF_APPROVE`` is kept as an enum
value only so audit rows written during that period still parse; no
transition reaches it any more.

Two roles decide the spec gate now:

* an **Engineer** submits and runs;
* an **Approver** is the only one who can move ``PENDING_APPROVAL`` to
  ``APPROVED`` (or back to ``DRAFT``) — see :mod:`planbench_api.accounts`.

Three capabilities:

* ``OWNER`` — created this benchmark;
* ``REVIEWER`` — named on the pending request for *this* action, and
  holds the Approver role (the caller enforces the role check when the
  request is created — see :mod:`planbench_api.review_service`);
* ``ADMIN`` — an operational override, not a benchmark role. Ordinary
  admin actions (recovery, unsticking a stale request) are written to
  the audit trail like anyone else's. The two ``ADMIN_OVERRIDE_*``
  actions are the one deliberate exception: they let an admin clear the
  spec gate without an Approver, for a solo deployment that has no
  second account to ask. They are gated a second time, at the service
  layer, behind ``PLANBENCH_ADMIN_OVERRIDE_ENABLED`` (off by default),
  and always recorded under their own action name so the trail never
  claims a real review happened.

The state machine stays pure. Whether a pending review blocks the owner
is a question about stored review requests, so the *caller* computes the
capability set and this module only validates the transition. Keeping
the two apart is what lets the machine be tested without a database.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    """What an account is, for audit purposes only — not used to decide
    what an action may do (:class:`Capability` does that).

    ``MEMBER``, ``OPERATOR`` and ``REVIEWER`` are retained so audit rows
    written before this and the prior refactor still parse. Nothing
    assigns them any more: a current row logs ``ENGINEER``, ``APPROVER``
    or ``ADMIN``, matching :class:`planbench_api.accounts.UserRole` (plus
    the separate ``is_admin`` override).
    """

    ENGINEER = "engineer"
    APPROVER = "approver"
    ADMIN = "admin"
    MEMBER = "member"
    OPERATOR = "operator"
    REVIEWER = "reviewer"


class Capability(StrEnum):
    """Why the caller is allowed to act on this particular benchmark."""

    OWNER = "owner"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class BenchmarkState(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Action(StrEnum):
    SUBMIT = "submit"
    #: No longer reachable — see the module docstring. Kept so audit rows
    #: from before this refactor still parse.
    SELF_APPROVE = "self_approved"
    APPROVE = "approve"
    REJECT = "reject"
    #: An admin clearing the spec gate without an Approver. Its own name,
    #: never APPROVE, so the trail never claims a second person reviewed
    #: it. Gated behind PLANBENCH_ADMIN_OVERRIDE_ENABLED at the service
    #: layer — see planbench_api.services.BenchmarkService.admin_override.
    ADMIN_OVERRIDE_APPROVE = "admin_override_approve"
    ADMIN_OVERRIDE_REJECT = "admin_override_reject"
    RUN = "run"
    CANCEL = "cancel"
    COMPLETE = "complete"
    FAIL = "fail"
    ACCEPT_RESULT = "accept_result"
    REJECT_RESULT = "reject_result"
    #: Review bookkeeping. These leave the state untouched and exist so
    #: asking for, and withdrawing, a review are in the same audit trail
    #: as everything else.
    REQUEST_REVIEW = "request_review"
    CANCEL_REVIEW = "cancel_review"


OWNER_ONLY = frozenset({Capability.OWNER, Capability.ADMIN})
#: Deliberately *no* ADMIN fallback, unlike the other capability sets in
#: this module. APPROVE/REJECT are the spec-review gate itself — if an
#: admin could reach them directly, "admin approved it" would be
#: indistinguishable in the audit trail from "an Approver reviewed it",
#: which is exactly the ambiguity ADMIN_OVERRIDE_APPROVE/REJECT exist to
#: avoid. An admin who needs to clear this gate uses those instead, and
#: only when PLANBENCH_ADMIN_OVERRIDE_ENABLED says so.
REVIEWER_ONLY = frozenset({Capability.REVIEWER})
OWNER_OR_REVIEWER = frozenset({Capability.OWNER, Capability.REVIEWER, Capability.ADMIN})
#: Strictly the admin override — no fallback to OWNER or REVIEWER, unlike
#: the sets above where ADMIN is *also* accepted alongside the normal
#: capability. This is the one action where being an admin is the only
#: acceptable reason to be here at all.
ADMIN_ONLY = frozenset({Capability.ADMIN})

# action -> (allowed source states, target state, capabilities permitted)
TRANSITIONS: dict[Action, tuple[frozenset[BenchmarkState], BenchmarkState | None, frozenset]] = {
    Action.SUBMIT: (
        frozenset({BenchmarkState.DRAFT, BenchmarkState.REJECTED}),
        BenchmarkState.PENDING_APPROVAL,
        OWNER_ONLY,
    ),
    # No capability permits this any more — see the module docstring.
    # Kept in the table (rather than removed) so a caller that somehow
    # still reaches it gets PermissionDenied, not a KeyError.
    Action.SELF_APPROVE: (
        frozenset({BenchmarkState.DRAFT, BenchmarkState.REJECTED, BenchmarkState.PENDING_APPROVAL}),
        BenchmarkState.APPROVED,
        frozenset(),
    ),
    Action.APPROVE: (
        frozenset({BenchmarkState.PENDING_APPROVAL}),
        BenchmarkState.APPROVED,
        REVIEWER_ONLY,
    ),
    Action.REJECT: (
        frozenset({BenchmarkState.PENDING_APPROVAL}),
        BenchmarkState.DRAFT,
        REVIEWER_ONLY,
    ),
    Action.ADMIN_OVERRIDE_APPROVE: (
        frozenset(
            {BenchmarkState.DRAFT, BenchmarkState.REJECTED, BenchmarkState.PENDING_APPROVAL}
        ),
        BenchmarkState.APPROVED,
        ADMIN_ONLY,
    ),
    Action.ADMIN_OVERRIDE_REJECT: (
        frozenset({BenchmarkState.PENDING_APPROVAL}),
        BenchmarkState.DRAFT,
        ADMIN_ONLY,
    ),
    Action.RUN: (
        frozenset({BenchmarkState.APPROVED}),
        BenchmarkState.RUNNING,
        OWNER_ONLY,
    ),
    Action.COMPLETE: (
        frozenset({BenchmarkState.RUNNING}),
        BenchmarkState.PENDING_REVIEW,
        OWNER_ONLY,
    ),
    Action.FAIL: (
        frozenset({BenchmarkState.RUNNING}),
        BenchmarkState.FAILED,
        OWNER_ONLY,
    ),
    Action.CANCEL: (
        frozenset(
            {BenchmarkState.APPROVED, BenchmarkState.RUNNING, BenchmarkState.PENDING_APPROVAL}
        ),
        BenchmarkState.CANCELLED,
        OWNER_ONLY,
    ),
    # The owner is listed here, but the *caller* withholds OWNER while a
    # result review is pending — see the module docstring.
    Action.ACCEPT_RESULT: (
        frozenset({BenchmarkState.PENDING_REVIEW}),
        BenchmarkState.ACCEPTED,
        OWNER_OR_REVIEWER,
    ),
    Action.REJECT_RESULT: (
        frozenset({BenchmarkState.PENDING_REVIEW}),
        BenchmarkState.REJECTED,
        OWNER_OR_REVIEWER,
    ),
    # Bookkeeping: allowed from any state, and the state does not move.
    Action.REQUEST_REVIEW: (frozenset(BenchmarkState), None, OWNER_ONLY),
    Action.CANCEL_REVIEW: (frozenset(BenchmarkState), None, OWNER_ONLY),
}


class TransitionError(Exception):
    """The requested transition is not allowed from the current state."""


class PermissionDenied(Exception):
    """The caller holds no capability that permits this action."""


class ApprovalRecord(BaseModel):
    """Audit entry for one lifecycle event.

    ``user_id`` is the identity that matters; ``user`` is the nickname at
    the time, kept so the trail stays readable after a rename. Rows
    written before the refactor have no ``user_id`` and default to empty
    rather than failing to load.
    """

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    user: str
    role: Role
    action: Action
    previous_state: BenchmarkState
    new_state: BenchmarkState
    comment: str = ""
    timestamp: str
    user_id: str = ""
    #: Set when the event came from answering a review request, so an
    #: approval can be traced back to the request that asked for it.
    review_request_id: str | None = None


def next_state(
    current: BenchmarkState,
    action: Action,
    capabilities: frozenset[Capability] | set[Capability],
) -> BenchmarkState:
    """Validate a transition and return the resulting state.

    Bookkeeping actions return ``current`` unchanged.

    Raises:
        PermissionDenied: the caller holds none of the required capabilities.
        TransitionError: the action is not allowed from ``current``.
    """
    allowed_from, target, permitted = TRANSITIONS[action]
    if not permitted & set(capabilities):
        raise PermissionDenied(
            f"{action.value!r} requires one of "
            f"{sorted(capability.value for capability in permitted)}; "
            f"caller has {sorted(capability.value for capability in capabilities) or 'none'}"
        )
    if current not in allowed_from:
        raise TransitionError(
            f"cannot {action.value} a benchmark in state {current.value!r} "
            f"(allowed states: {sorted(state.value for state in allowed_from)})"
        )
    return target if target is not None else current


__all__ = [
    "ADMIN_ONLY",
    "OWNER_ONLY",
    "OWNER_OR_REVIEWER",
    "REVIEWER_ONLY",
    "TRANSITIONS",
    "Action",
    "ApprovalRecord",
    "BenchmarkState",
    "Capability",
    "PermissionDenied",
    "Role",
    "TransitionError",
    "next_state",
]
