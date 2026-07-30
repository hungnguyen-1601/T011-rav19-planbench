"""Unit tests for the benchmark approval state machine."""

from __future__ import annotations

import pytest

from planbench_api.approval import (
    Action,
    BenchmarkState,
    PermissionDenied,
    Role,
    TransitionError,
    next_state,
)

CREATOR = "op-alice"
OTHER_OPERATOR = "op-bob"
REVIEWER = "rev-carol"


def transition(
    current: BenchmarkState, action: Action, role: Role, actor: str = REVIEWER
) -> BenchmarkState:
    return next_state(current, action, role, actor=actor, created_by=CREATOR)


class TestHappyPath:
    def test_full_lifecycle(self) -> None:
        state = BenchmarkState.DRAFT
        state = transition(state, Action.SUBMIT, Role.OPERATOR, actor=CREATOR)
        assert state is BenchmarkState.PENDING_APPROVAL
        state = transition(state, Action.APPROVE, Role.REVIEWER)
        assert state is BenchmarkState.APPROVED
        state = transition(state, Action.RUN, Role.OPERATOR, actor=CREATOR)
        assert state is BenchmarkState.RUNNING
        state = transition(state, Action.COMPLETE, Role.OPERATOR, actor=CREATOR)
        assert state is BenchmarkState.PENDING_REVIEW
        state = transition(state, Action.ACCEPT_RESULT, Role.REVIEWER)
        assert state is BenchmarkState.ACCEPTED

    def test_rejected_spec_returns_to_draft(self) -> None:
        state = transition(BenchmarkState.PENDING_APPROVAL, Action.REJECT, Role.REVIEWER)
        assert state is BenchmarkState.DRAFT

    def test_rejected_result_can_be_resubmitted(self) -> None:
        state = transition(BenchmarkState.PENDING_REVIEW, Action.REJECT_RESULT, Role.REVIEWER)
        assert state is BenchmarkState.REJECTED
        assert (
            transition(state, Action.SUBMIT, Role.OPERATOR, actor=CREATOR)
            is BenchmarkState.PENDING_APPROVAL
        )

    def test_failure_during_execution(self) -> None:
        assert (
            transition(BenchmarkState.RUNNING, Action.FAIL, Role.OPERATOR, actor=CREATOR)
            is BenchmarkState.FAILED
        )

    @pytest.mark.parametrize(
        "state",
        [BenchmarkState.PENDING_APPROVAL, BenchmarkState.APPROVED, BenchmarkState.RUNNING],
    )
    def test_cancellable_states(self, state: BenchmarkState) -> None:
        assert (
            transition(state, Action.CANCEL, Role.OPERATOR, actor=CREATOR)
            is BenchmarkState.CANCELLED
        )


class TestGates:
    def test_draft_cannot_run(self) -> None:
        with pytest.raises(TransitionError, match="cannot run"):
            transition(BenchmarkState.DRAFT, Action.RUN, Role.OPERATOR, actor=CREATOR)

    def test_pending_approval_cannot_run(self) -> None:
        """Gate 1: an unapproved spec must never execute."""
        with pytest.raises(TransitionError):
            transition(BenchmarkState.PENDING_APPROVAL, Action.RUN, Role.OPERATOR, actor=CREATOR)

    def test_results_cannot_be_accepted_before_completion(self) -> None:
        with pytest.raises(TransitionError):
            transition(BenchmarkState.RUNNING, Action.ACCEPT_RESULT, Role.REVIEWER)

    def test_completed_benchmark_cannot_rerun(self) -> None:
        with pytest.raises(TransitionError):
            transition(BenchmarkState.PENDING_REVIEW, Action.RUN, Role.OPERATOR, actor=CREATOR)


class TestPermissions:
    def test_operator_cannot_approve(self) -> None:
        with pytest.raises(PermissionDenied, match="may not perform"):
            transition(
                BenchmarkState.PENDING_APPROVAL,
                Action.APPROVE,
                Role.OPERATOR,
                actor=OTHER_OPERATOR,
            )

    def test_reviewer_cannot_submit(self) -> None:
        with pytest.raises(PermissionDenied):
            transition(BenchmarkState.DRAFT, Action.SUBMIT, Role.REVIEWER)

    def test_reviewer_cannot_run(self) -> None:
        with pytest.raises(PermissionDenied):
            transition(BenchmarkState.APPROVED, Action.RUN, Role.REVIEWER)

    def test_self_review_blocked(self) -> None:
        """Separation of duties: the creator may not review their own work."""
        with pytest.raises(PermissionDenied, match="separation of duties"):
            next_state(
                BenchmarkState.PENDING_APPROVAL,
                Action.APPROVE,
                Role.REVIEWER,
                actor=CREATOR,
                created_by=CREATOR,
            )

    def test_admin_is_exempt_from_self_review_rule(self) -> None:
        assert (
            next_state(
                BenchmarkState.PENDING_APPROVAL,
                Action.APPROVE,
                Role.ADMIN,
                actor=CREATOR,
                created_by=CREATOR,
            )
            is BenchmarkState.APPROVED
        )

    def test_a_different_reviewer_may_approve(self) -> None:
        assert (
            transition(BenchmarkState.PENDING_APPROVAL, Action.APPROVE, Role.REVIEWER)
            is BenchmarkState.APPROVED
        )
