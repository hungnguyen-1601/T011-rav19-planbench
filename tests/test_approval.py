"""Unit tests for the benchmark state machine.

The machine takes a capability set, not a role and an actor name. That
is the point of the refactor: *why* the caller is allowed to act — they
own it, they were asked to review it, they are an admin — is decided
where the benchmark and its review requests are, and the machine only
answers "is this transition legal for a caller holding these".

So these tests are about states and edges. Whether the owner still holds
OWNER while a review is pending is a service question, tested in
tests/api/test_api_reviews.py.
"""

from __future__ import annotations

import pytest

from planbench_api.approval import (
    Action,
    BenchmarkState,
    Capability,
    PermissionDenied,
    TransitionError,
    next_state,
)

OWNER = frozenset({Capability.OWNER})
REVIEWER = frozenset({Capability.REVIEWER})
ADMIN = frozenset({Capability.ADMIN})
NOBODY = frozenset()


class TestSoloPath:
    """The default: one member, no reviewer, start to finish."""

    def test_owner_carries_a_benchmark_to_accepted_alone(self) -> None:
        state = BenchmarkState.DRAFT
        state = next_state(state, Action.SELF_APPROVE, OWNER)
        assert state is BenchmarkState.APPROVED
        state = next_state(state, Action.RUN, OWNER)
        assert state is BenchmarkState.RUNNING
        state = next_state(state, Action.COMPLETE, OWNER)
        assert state is BenchmarkState.PENDING_REVIEW
        state = next_state(state, Action.ACCEPT_RESULT, OWNER)
        assert state is BenchmarkState.ACCEPTED

    def test_self_approve_also_clears_a_spec_that_was_submitted(self) -> None:
        """Submitting and then deciding to run it yourself must work."""
        state = next_state(BenchmarkState.DRAFT, Action.SUBMIT, OWNER)
        assert state is BenchmarkState.PENDING_APPROVAL
        assert next_state(state, Action.SELF_APPROVE, OWNER) is BenchmarkState.APPROVED

    def test_a_rejected_benchmark_can_go_round_again(self) -> None:
        state = next_state(BenchmarkState.PENDING_REVIEW, Action.REJECT_RESULT, REVIEWER)
        assert state is BenchmarkState.REJECTED
        assert next_state(state, Action.SELF_APPROVE, OWNER) is BenchmarkState.APPROVED


class TestReviewedPath:
    def test_a_reviewer_clears_the_spec_gate(self) -> None:
        state = next_state(BenchmarkState.DRAFT, Action.SUBMIT, OWNER)
        assert next_state(state, Action.APPROVE, REVIEWER) is BenchmarkState.APPROVED

    def test_a_rejected_spec_returns_to_draft(self) -> None:
        assert (
            next_state(BenchmarkState.PENDING_APPROVAL, Action.REJECT, REVIEWER)
            is BenchmarkState.DRAFT
        )

    def test_a_reviewer_accepts_results(self) -> None:
        assert (
            next_state(BenchmarkState.PENDING_REVIEW, Action.ACCEPT_RESULT, REVIEWER)
            is BenchmarkState.ACCEPTED
        )


class TestBookkeeping:
    """Asking for and withdrawing review are audited, not transitions."""

    @pytest.mark.parametrize("state", list(BenchmarkState))
    def test_requesting_a_review_never_moves_the_state(self, state: BenchmarkState) -> None:
        assert next_state(state, Action.REQUEST_REVIEW, OWNER) is state

    @pytest.mark.parametrize("state", list(BenchmarkState))
    def test_cancelling_a_review_never_moves_the_state(self, state: BenchmarkState) -> None:
        assert next_state(state, Action.CANCEL_REVIEW, OWNER) is state

    def test_only_the_owner_may_ask(self) -> None:
        with pytest.raises(PermissionDenied):
            next_state(BenchmarkState.DRAFT, Action.REQUEST_REVIEW, REVIEWER)


class TestGates:
    def test_a_draft_cannot_run(self) -> None:
        with pytest.raises(TransitionError, match="cannot run"):
            next_state(BenchmarkState.DRAFT, Action.RUN, OWNER)

    def test_an_unapproved_spec_cannot_run(self) -> None:
        """Gate 1 survived the refactor: approval is still required."""
        with pytest.raises(TransitionError):
            next_state(BenchmarkState.PENDING_APPROVAL, Action.RUN, OWNER)

    def test_results_cannot_be_accepted_before_completion(self) -> None:
        with pytest.raises(TransitionError):
            next_state(BenchmarkState.RUNNING, Action.ACCEPT_RESULT, OWNER)

    def test_a_finished_benchmark_cannot_rerun(self) -> None:
        with pytest.raises(TransitionError):
            next_state(BenchmarkState.PENDING_REVIEW, Action.RUN, OWNER)

    def test_failure_during_execution(self) -> None:
        assert next_state(BenchmarkState.RUNNING, Action.FAIL, OWNER) is BenchmarkState.FAILED

    @pytest.mark.parametrize(
        "state",
        [BenchmarkState.PENDING_APPROVAL, BenchmarkState.APPROVED, BenchmarkState.RUNNING],
    )
    def test_cancellable_states(self, state: BenchmarkState) -> None:
        assert next_state(state, Action.CANCEL, OWNER) is BenchmarkState.CANCELLED


class TestCapabilities:
    def test_a_caller_with_no_capability_can_do_nothing(self) -> None:
        with pytest.raises(PermissionDenied, match="caller has none"):
            next_state(BenchmarkState.DRAFT, Action.SELF_APPROVE, NOBODY)

    def test_a_reviewer_cannot_run_the_benchmark_they_reviewed(self) -> None:
        """Reviewing is not a licence to operate somebody else's work."""
        with pytest.raises(PermissionDenied):
            next_state(BenchmarkState.APPROVED, Action.RUN, REVIEWER)

    def test_a_reviewer_cannot_submit(self) -> None:
        with pytest.raises(PermissionDenied):
            next_state(BenchmarkState.DRAFT, Action.SUBMIT, REVIEWER)

    def test_the_owner_alone_cannot_answer_a_review(self) -> None:
        """APPROVE is the reviewer's edge; the owner's is SELF_APPROVE."""
        with pytest.raises(PermissionDenied):
            next_state(BenchmarkState.PENDING_APPROVAL, Action.APPROVE, OWNER)

    @pytest.mark.parametrize(
        "action",
        [Action.SELF_APPROVE, Action.APPROVE, Action.RUN, Action.REQUEST_REVIEW],
    )
    def test_an_admin_can_perform_any_action(self, action: Action) -> None:
        """Recovery is possible; it is also always in the audit trail."""
        state = BenchmarkState.APPROVED if action is Action.RUN else BenchmarkState.PENDING_APPROVAL
        assert next_state(state, action, ADMIN) is not None
