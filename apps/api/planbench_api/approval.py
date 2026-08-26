"""Benchmark lifecycle: states, transitions and the audit trail.

    DRAFT ──self_approve──> APPROVED ──run──> RUNNING ──complete──> PENDING_REVIEW
      │                        ^                                          │
      └──submit──> PENDING_APPROVAL ──approve──┘             accept_result│└──reject_result──┐
                            │                                             v                  v
                            └──reject──> DRAFT                        ACCEPTED           REJECTED

The states are unchanged from the role-based design, so benchmarks
recorded before this refactor still load and still mean the same thing.
What changed is **who** may drive them.

Authority is ownership, not role. The person who created a benchmark can
carry it all the way to ACCEPTED on their own: that is the ordinary case
and it needs no second person. Review is opt-in — when the owner asks a
named member to look, that member becomes the only one who can answer,
and the owner loses the corresponding self-service action until they do.

Two capabilities therefore decide everything:

* ``OWNER`` — created this benchmark;
* ``REVIEWER`` — named on the pending request for *this* action.

``ADMIN`` exists for recovery and is deliberately not a benchmark role:
an admin acting here is written to the audit trail like anyone else, so
"an admin fixed it" is a visible event rather than an invisible one.

The state machine stays pure. Whether a pending review blocks the owner
is a question about stored review requests, so the *caller* computes the
capability set and this module only validates the transition. Keeping
the two apart is what lets the machine be tested without a database.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    """What an account is, for audit purposes.

    Only ``MEMBER`` and ``ADMIN`` are ever written now. The rest are
    retained so audit rows recorded by earlier versions still parse —
    an audit trail that cannot be read is not an audit trail, and the
    alternative (rewriting historical rows in a migration) would edit
    the record of who did what.

    ``ENGINEER`` and ``APPROVER`` are the oldest pair, from the original
    role-based design; ``OPERATOR`` and ``REVIEWER`` came next. Nothing
    assigns any of the four, and nothing branches on Role for
    authorisation — see the module docstring. A stored role is a label
    on a past event, never a permission.
    """

    MEMBER = "member"
    ADMIN = "admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    ENGINEER = "engineer"
    APPROVER = "approver"


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
    #: The owner clearing their own spec gate because nobody was asked to
    #: review it. Recorded distinctly from APPROVE so the audit trail
    #: never claims a second person looked.
    SELF_APPROVE = "self_approved"
    APPROVE = "approve"
    REJECT = "reject"
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
REVIEWER_ONLY = frozenset({Capability.REVIEWER, Capability.ADMIN})
OWNER_OR_REVIEWER = frozenset({Capability.OWNER, Capability.REVIEWER, Capability.ADMIN})

# action -> (allowed source states, target state, capabilities permitted)
TRANSITIONS: dict[Action, tuple[frozenset[BenchmarkState], BenchmarkState | None, frozenset]] = {
    Action.SUBMIT: (
        frozenset({BenchmarkState.DRAFT, BenchmarkState.REJECTED}),
        BenchmarkState.PENDING_APPROVAL,
        OWNER_ONLY,
    ),
    Action.SELF_APPROVE: (
        frozenset({BenchmarkState.DRAFT, BenchmarkState.REJECTED, BenchmarkState.PENDING_APPROVAL}),
        BenchmarkState.APPROVED,
        OWNER_ONLY,
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
