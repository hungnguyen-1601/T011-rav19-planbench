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


class ReviewSubject(StrEnum):
    """What a request is about.

    Two lanes with two rulebooks, sharing one table. The benchmark lane
    keeps named-reviewer semantics: only the person asked may answer, and
    there is no claiming. Rewriting the rules a stored benchmark was
    decided under would make its audit trail describe a process that
    never happened.
    """

    BENCHMARK = "benchmark"
    DECISION_RUN = "decision_run"


class ReviewStage(StrEnum):
    SPEC = "spec"
    RESULT = "result"


class ReviewStatus(StrEnum):
    #: Nobody has picked it up. Whether anybody *may* is
    #: ``available_to_pool`` — a directed request sits here too.
    OPEN = "open"
    #: Somebody is holding it. Only they may acknowledge or decide.
    CLAIMED = "claimed"
    #: Terminal, and **only** for a run that produced no Decision Card.
    #: Most comparisons rank nobody; they still say who was eliminated
    #: where, so somebody has to read them — but there is no
    #: configuration to approve, and calling that "approved" would put a
    #: verdict on a run that recommends nobody.
    ACKNOWLEDGED = "acknowledged"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    #: The spelling the benchmark lane has always used for "not answered
    #: yet". Kept so rows written before this load, and so the older
    #: lane's queries keep meaning what they meant.
    PENDING = "pending"


#: A request in any of these states is finished and cannot be answered
#: again. Kept as data so "is this still open?" has one definition.
TERMINAL_STATUSES = frozenset(
    {
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.CANCELLED,
        ReviewStatus.ACKNOWLEDGED,
    }
)

#: Somebody could still act on it. The complement of terminal, written
#: out so "is this still open?" has one definition rather than a
#: negation somebody has to re-derive.
LIVE_STATUSES = frozenset(
    {ReviewStatus.OPEN, ReviewStatus.CLAIMED, ReviewStatus.PENDING}
)


class ReviewError(Exception):
    """The review request cannot be created or answered as asked."""


class ReviewNotAllowed(ReviewError):
    """The caller is not the person this request is waiting on."""


class ReviewConflict(ReviewError):
    """Somebody else got there first.

    Its own class because the caller's next move differs: a conflict is
    answered by reloading and looking again, not by asking for a
    different permission.
    """


class ReviewRequest(BaseModel):
    """One request for a second opinion."""

    model_config = ConfigDict(frozen=True)

    id: str
    benchmark_id: str = ""
    subject_kind: ReviewSubject = ReviewSubject.BENCHMARK
    subject_id: str = ""
    stage: ReviewStage = ReviewStage.RESULT
    requested_by_user_id: str = ""
    #: What the requester asked for. Never cleared, even after somebody
    #: else takes the request over: it is part of what they said, and an
    #: engineer looking at their own request should still see who they
    #: addressed it to.
    requested_reviewer_user_id: str | None = None
    #: Where it is now. ``None`` means nobody is holding it.
    claimed_by_user_id: str | None = None
    claimed_at: str | None = None
    #: Whether anybody with the capability may claim it. Stated rather
    #: than inferred from the two fields above — inferring it is what
    #: left a directed request stuck the moment its reviewer released it.
    available_to_pool: bool = False
    #: The old name for the reviewer, still written for the benchmark
    #: lane so its queries and its stored rows keep agreeing.
    reviewer_user_id: str = ""
    status: ReviewStatus = ReviewStatus.PENDING
    request_comment: str = ""
    review_comment: str = ""
    created_at: str = ""
    reviewed_at: str | None = None
    cancelled_at: str | None = None

    @property
    def is_pending(self) -> bool:
        """Still answerable. Named for the benchmark lane's vocabulary."""
        return self.status in LIVE_STATUSES

    @property
    def subject(self) -> str:
        """What it is about, whichever lane wrote it."""
        return self.subject_id or self.benchmark_id

    def claimable_by(self, user_id: str) -> bool:
        """Whether this person may pick it up without taking it over.

        Two ways in: the pool is open, or they are the person the
        requester named. Anything else is a takeover, which is a
        different act and carries a reason.
        """
        if self.claimed_by_user_id is not None:
            return False
        return self.available_to_pool or self.requested_reviewer_user_id == user_id

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
    "LIVE_STATUSES",
    "TERMINAL_STATUSES",
    "ReviewConflict",
    "ReviewSubject",
    "ReviewError",
    "ReviewNotAllowed",
    "ReviewRequest",
    "ReviewRequestView",
    "ReviewStage",
    "ReviewStatus",
    "blocking_stage",
]
