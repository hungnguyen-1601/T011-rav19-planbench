"""Benchmark lifecycle: states, transitions and approval records.

The state machine encodes the human-in-the-loop rules from the spec:

    DRAFT ──submit──> PENDING_APPROVAL ──approve──> APPROVED ──run──> RUNNING
      ^                     │                          │                │
      └────── reject ───────┘                       cancel          completed
                                                                        │
                                            PENDING_REVIEW ──accept──> ACCEPTED
                                                   │
                                                   └──reject──> REJECTED

Two gates are mandatory (spec section 21):
1. A Reviewer approves the BenchmarkSpec before it may run.
2. A Reviewer accepts or rejects the conclusions afterwards.

Separation of duties: the Operator who created a benchmark may not
approve it (``ALLOW_SELF_APPROVAL`` is False and is not configurable at
runtime — loosening it is a deliberate code change).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

ALLOW_SELF_APPROVAL = False


class Role(StrEnum):
    OPERATOR = "operator"
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
    APPROVE = "approve"
    REJECT = "reject"
    RUN = "run"
    CANCEL = "cancel"
    COMPLETE = "complete"
    FAIL = "fail"
    ACCEPT_RESULT = "accept_result"
    REJECT_RESULT = "reject_result"


# action -> (allowed source states, target state, roles permitted)
TRANSITIONS: dict[Action, tuple[frozenset[BenchmarkState], BenchmarkState, frozenset[Role]]] = {
    Action.SUBMIT: (
        frozenset({BenchmarkState.DRAFT, BenchmarkState.REJECTED}),
        BenchmarkState.PENDING_APPROVAL,
        frozenset({Role.OPERATOR, Role.ADMIN}),
    ),
    Action.APPROVE: (
        frozenset({BenchmarkState.PENDING_APPROVAL}),
        BenchmarkState.APPROVED,
        frozenset({Role.REVIEWER, Role.ADMIN}),
    ),
    Action.REJECT: (
        frozenset({BenchmarkState.PENDING_APPROVAL}),
        BenchmarkState.DRAFT,
        frozenset({Role.REVIEWER, Role.ADMIN}),
    ),
    Action.RUN: (
        frozenset({BenchmarkState.APPROVED}),
        BenchmarkState.RUNNING,
        frozenset({Role.OPERATOR, Role.ADMIN}),
    ),
    Action.COMPLETE: (
        frozenset({BenchmarkState.RUNNING}),
        BenchmarkState.PENDING_REVIEW,
        frozenset({Role.OPERATOR, Role.ADMIN}),
    ),
    Action.FAIL: (
        frozenset({BenchmarkState.RUNNING}),
        BenchmarkState.FAILED,
        frozenset({Role.OPERATOR, Role.ADMIN}),
    ),
    Action.CANCEL: (
        frozenset(
            {BenchmarkState.APPROVED, BenchmarkState.RUNNING, BenchmarkState.PENDING_APPROVAL}
        ),
        BenchmarkState.CANCELLED,
        frozenset({Role.OPERATOR, Role.ADMIN}),
    ),
    Action.ACCEPT_RESULT: (
        frozenset({BenchmarkState.PENDING_REVIEW}),
        BenchmarkState.ACCEPTED,
        frozenset({Role.REVIEWER, Role.ADMIN}),
    ),
    Action.REJECT_RESULT: (
        frozenset({BenchmarkState.PENDING_REVIEW}),
        BenchmarkState.REJECTED,
        frozenset({Role.REVIEWER, Role.ADMIN}),
    ),
}


class TransitionError(Exception):
    """The requested transition is not allowed from the current state."""


class PermissionDenied(Exception):
    """The user's role may not perform this action."""


class ApprovalRecord(BaseModel):
    """Audit entry for one lifecycle transition."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    user: str
    role: Role
    action: Action
    previous_state: BenchmarkState
    new_state: BenchmarkState
    comment: str = ""
    timestamp: str


def next_state(
    current: BenchmarkState,
    action: Action,
    role: Role,
    *,
    actor: str,
    created_by: str,
) -> BenchmarkState:
    """Validate a transition and return the resulting state.

    Raises:
        PermissionDenied: role not allowed, or self-approval attempted.
        TransitionError: action not allowed from ``current``.
    """
    allowed_from, target, roles = TRANSITIONS[action]
    if role not in roles:
        raise PermissionDenied(
            f"role {role.value!r} may not perform {action.value!r} "
            f"(allowed: {sorted(r.value for r in roles)})"
        )
    if current not in allowed_from:
        raise TransitionError(
            f"cannot {action.value} a benchmark in state {current.value!r} "
            f"(allowed states: {sorted(s.value for s in allowed_from)})"
        )
    review_actions = {Action.APPROVE, Action.REJECT, Action.ACCEPT_RESULT, Action.REJECT_RESULT}
    if (
        action in review_actions
        and not ALLOW_SELF_APPROVAL
        and actor == created_by
        and role is not Role.ADMIN
    ):
        raise PermissionDenied(
            "separation of duties: the operator who created a benchmark cannot review it"
        )
    return target
