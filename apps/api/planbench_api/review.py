"""Optional peer review.

Review is a request from one member to another, not a stage every
benchmark must pass. The default path has no reviewer in it at all:
create, run, accept, done. Asking for review is a deliberate act, and
until somebody asks, nothing waits on anyone.

Two stages, because they answer different questions at different times:

* ``spec`` — "is this experiment set up correctly?", asked *before* the
  run. A pending spec review blocks the run: the point is to catch a bad
  setup before spending the compute, and running anyway would make the
  review pointless.
* ``result`` — "do you agree with what came out?", asked *after*. A
  pending result review blocks self-accept, so the answer to "has this
  been checked?" cannot be yes-by-default.

Only the named reviewer can answer. Not the owner, not another member,
not somebody who happens to know the request id. That single rule is
what makes an approval mean anything — without it, "reviewed" would
degrade into "the owner clicked the other button".
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from planbench_api.accounts import UserSummary, now_iso


class ReviewStage(StrEnum):
    SPEC = "spec"
    RESULT = "result"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


#: A request in any of these states is finished and cannot be answered
#: again. Kept as data so "is this still open?" has one definition.
TERMINAL_STATUSES = frozenset(
    {ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.CANCELLED}
)


class ReviewError(Exception):
    """The review request cannot be created or answered as asked."""


class ReviewNotAllowed(ReviewError):
    """The caller is not the person this request was addressed to."""


class ReviewRequest(BaseModel):
    """One request for a second opinion."""

    model_config = ConfigDict(frozen=True)

    id: str
    benchmark_id: str
    stage: ReviewStage
    requested_by_user_id: str
    reviewer_user_id: str
    status: ReviewStatus = ReviewStatus.PENDING
    request_comment: str = ""
    review_comment: str = ""
    created_at: str = ""
    reviewed_at: str | None = None
    cancelled_at: str | None = None

    @property
    def is_pending(self) -> bool:
        return self.status is ReviewStatus.PENDING

    def answered(self, status: ReviewStatus, comment: str = "") -> ReviewRequest:
        """A copy in a terminal state, stamped with the time."""
        field = "cancelled_at" if status is ReviewStatus.CANCELLED else "reviewed_at"
        return self.model_copy(
            update={
                "status": status,
                "review_comment": comment or self.review_comment,
                field: now_iso(),
            }
        )


class ReviewRequestView(BaseModel):
    """A request with the people resolved, for inbox and detail views.

    The API returns nicknames so a human can read the list; permission
    checks upstream still use the ids on :class:`ReviewRequest`.
    """

    model_config = ConfigDict(frozen=True)

    request: ReviewRequest
    benchmark_name: str = ""
    benchmark_state: str = ""
    requested_by: UserSummary | None = None
    reviewer: UserSummary | None = None


def blocking_stage(requests: list[ReviewRequest], stage: ReviewStage) -> ReviewRequest | None:
    """The pending request that gates ``stage``, if there is one."""
    for request in requests:
        if request.stage is stage and request.is_pending:
            return request
    return None


__all__ = [
    "TERMINAL_STATUSES",
    "ReviewError",
    "ReviewNotAllowed",
    "ReviewRequest",
    "ReviewRequestView",
    "ReviewStage",
    "ReviewStatus",
    "blocking_stage",
]
