"""Sending, answering and withdrawing review requests.

The rules here are small and all of them are about the same thing: an
approval only means something if the person who wanted it could not have
produced it themselves.

* the owner asks, and only the owner may ask or withdraw;
* only a member with the Approver role (or an admin) can be named —
  asking an Engineer to review would make the gate decorative;
* a member cannot review their own benchmark;
* only the named reviewer may answer, and only once;
* one pending request per stage, so "who is this waiting on?" has one
  answer.

Answering is not the same as changing benchmark state. This service
records the decision on the request; the benchmark service applies the
resulting transition with the reviewer's capability. Splitting them
keeps a rejected review from silently rewriting a benchmark's state, and
keeps the state machine the only place transitions happen.
"""

from __future__ import annotations

import logging

from planbench_api.accounts import User, UserRole, UserSummary, now_iso
from planbench_api.errors import NotFoundError
from planbench_api.repository_ports import (
    BenchmarkRepositoryPort,
    ReviewRepositoryPort,
    UserRepositoryPort,
)
from planbench_api.review import (
    ReviewError,
    ReviewNotAllowed,
    ReviewRequest,
    ReviewRequestView,
    ReviewStage,
    ReviewStatus,
    blocking_stage,
)

logger = logging.getLogger("planbench.api.reviews")


class ReviewService:
    def __init__(
        self,
        reviews: ReviewRepositoryPort,
        users: UserRepositoryPort,
        benchmarks: BenchmarkRepositoryPort,
    ) -> None:
        self._reviews = reviews
        self._users = users
        self._benchmarks = benchmarks

    # -- queries -------------------------------------------------------

    def get_request(self, request_id: str) -> ReviewRequest:
        return self._reviews.get(request_id)

    def for_benchmark(self, benchmark_id: str) -> list[ReviewRequest]:
        return self._reviews.list_for_benchmark(benchmark_id)

    def pending(self, benchmark_id: str, stage: ReviewStage) -> ReviewRequest | None:
        return blocking_stage(self._reviews.list_for_benchmark(benchmark_id), stage)

    def inbox(self, user: User, pending_only: bool = False) -> list[ReviewRequestView]:
        status = ReviewStatus.PENDING if pending_only else None
        return [self.view(request) for request in self._reviews.list_for_reviewer(user.id, status)]

    def sent(self, user: User) -> list[ReviewRequestView]:
        return [self.view(request) for request in self._reviews.list_requested_by(user.id)]

    def pending_count(self, user: User) -> int:
        return len(self._reviews.list_for_reviewer(user.id, ReviewStatus.PENDING))

    def view(self, request: ReviewRequest) -> ReviewRequestView:
        return ReviewRequestView(
            request=request,
            benchmark_name=self._benchmark_name(request.benchmark_id),
            benchmark_state=self._benchmark_state(request.benchmark_id),
            requested_by=self._summary(request.requested_by_user_id),
            reviewer=self._summary(request.reviewer_user_id),
        )

    # -- commands ------------------------------------------------------

    def request(
        self,
        *,
        benchmark_id: str,
        stage: ReviewStage,
        requester: User,
        reviewer_nickname: str,
        comment: str = "",
    ) -> ReviewRequest:
        reviewer = self._users.find_by_nickname(reviewer_nickname)
        if reviewer is None:
            raise ReviewError(f"no member with the nickname {reviewer_nickname!r}")
        if reviewer.id == requester.id:
            raise ReviewError("you cannot send a review request to yourself")
        if reviewer.role is not UserRole.APPROVER and not reviewer.is_admin:
            raise ReviewError(
                f"{reviewer_nickname!r} is not an Approver; only an Approver can be asked to review"
            )
        if blocking_stage(self._reviews.list_for_benchmark(benchmark_id), stage) is not None:
            raise ReviewError(
                f"a {stage.value} review is already pending on this benchmark; "
                "cancel it before sending another"
            )
        request = self._reviews.create(
            ReviewRequest(
                id="",
                benchmark_id=benchmark_id,
                stage=stage,
                requested_by_user_id=requester.id,
                reviewer_user_id=reviewer.id,
                request_comment=comment,
                created_at=now_iso(),
            )
        )
        logger.info(
            "review requested",
            extra={
                "context": {
                    "benchmark_id": benchmark_id,
                    "stage": stage.value,
                    "request_id": request.id,
                    "requested_by": requester.id,
                    "reviewer": reviewer.id,
                }
            },
        )
        return request

    def answer(
        self, request_id: str, reviewer: User, status: ReviewStatus, comment: str = ""
    ) -> ReviewRequest:
        """Approve or reject. Only the named reviewer, only while pending."""
        request = self._reviews.get(request_id)
        if request.reviewer_user_id != reviewer.id:
            # Same message whoever asks, including the owner: the request
            # id is not a secret, and confirming who it belongs to is not
            # this endpoint's job.
            raise ReviewNotAllowed("this review request was not sent to you")
        if not request.is_pending:
            raise ReviewError(f"this review request is already {request.status.value}")
        answered = self._reviews.save(request.answered(status, comment))
        logger.info(
            "review answered",
            extra={
                "context": {
                    "request_id": request_id,
                    "status": status.value,
                    "reviewer": reviewer.id,
                }
            },
        )
        return answered

    def comment(self, request_id: str, author: User, comment: str) -> ReviewRequest:
        """Add a note without deciding. Either party may.

        Kept separate from answering so a reviewer can ask a question
        without the request leaving the pending state — otherwise the
        only way to say "what does this seed do?" is to reject.
        """
        request = self._reviews.get(request_id)
        if author.id not in {request.reviewer_user_id, request.requested_by_user_id}:
            raise ReviewNotAllowed("you are not part of this review request")
        if not comment.strip():
            raise ReviewError("a comment cannot be empty")
        existing = request.review_comment
        stamped = f"{author.label}: {comment.strip()}"
        merged = f"{existing}\n{stamped}" if existing else stamped
        return self._reviews.save(request.model_copy(update={"review_comment": merged}))

    def cancel(self, request_id: str, requester: User) -> ReviewRequest:
        """Withdraw a request. Only the person who sent it."""
        request = self._reviews.get(request_id)
        if request.requested_by_user_id != requester.id:
            raise ReviewNotAllowed("only the member who sent this request can cancel it")
        if not request.is_pending:
            raise ReviewError(f"this review request is already {request.status.value}")
        return self._reviews.save(request.answered(ReviewStatus.CANCELLED))

    # -- helpers -------------------------------------------------------

    def _summary(self, user_id: str) -> UserSummary | None:
        try:
            return UserSummary.of(self._users.get(user_id))
        except NotFoundError:
            # A deleted account must not make the whole inbox unreadable.
            return None

    def _benchmark_name(self, benchmark_id: str) -> str:
        try:
            return self._benchmarks.get(benchmark_id).spec.name
        except NotFoundError:
            return ""

    def _benchmark_state(self, benchmark_id: str) -> str:
        try:
            return self._benchmarks.get(benchmark_id).state.value
        except NotFoundError:
            return ""


__all__ = ["ReviewService"]
