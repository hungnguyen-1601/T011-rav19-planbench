"""The review inbox, and answering the requests in it.

Every route here resolves the caller from their token and compares it to
the ids stored on the request. Nothing is authorized by nickname: a
nickname is how the sender found this person, not proof of being them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from planbench_api.auth import ActiveUser
from planbench_api.dependencies import get_benchmark_service, get_review_service
from planbench_api.review import ReviewRequestView, ReviewStatus
from planbench_api.review_service import ReviewService
from planbench_api.services import BenchmarkService

router = APIRouter(prefix="/reviews", tags=["reviews"])

Reviews = Annotated[ReviewService, Depends(get_review_service)]
Benchmarks = Annotated[BenchmarkService, Depends(get_benchmark_service)]


class DecisionRequest(BaseModel):
    comment: str = ""


class CommentRequest(BaseModel):
    comment: str


class InboxResponse(BaseModel):
    requests: list[ReviewRequestView]
    pending: int


@router.get("/inbox", response_model=InboxResponse)
def inbox(reviews: Reviews, user: ActiveUser, pending_only: bool = False) -> InboxResponse:
    """Requests addressed to me. ``pending`` drives the sidebar badge."""
    return InboxResponse(
        requests=reviews.inbox(user, pending_only=pending_only),
        pending=reviews.pending_count(user),
    )


@router.get("/sent", response_model=list[ReviewRequestView])
def sent(reviews: Reviews, user: ActiveUser) -> list[ReviewRequestView]:
    return reviews.sent(user)


@router.post("/{request_id}/approve", response_model=ReviewRequestView)
def approve(
    request_id: str,
    payload: DecisionRequest,
    reviews: Reviews,
    benchmarks: Benchmarks,
    user: ActiveUser,
) -> ReviewRequestView:
    _stored, answered = benchmarks.answer_review(
        request_id, user, ReviewStatus.APPROVED, payload.comment
    )
    return reviews.view(answered)


@router.post("/{request_id}/reject", response_model=ReviewRequestView)
def reject(
    request_id: str,
    payload: DecisionRequest,
    reviews: Reviews,
    benchmarks: Benchmarks,
    user: ActiveUser,
) -> ReviewRequestView:
    _stored, answered = benchmarks.answer_review(
        request_id, user, ReviewStatus.REJECTED, payload.comment
    )
    return reviews.view(answered)


@router.post("/{request_id}/comment", response_model=ReviewRequestView)
def comment(
    request_id: str, payload: CommentRequest, reviews: Reviews, user: ActiveUser
) -> ReviewRequestView:
    """Say something without deciding; the request stays pending."""
    return reviews.view(reviews.comment(request_id, user, payload.comment))


@router.post("/{request_id}/cancel", response_model=ReviewRequestView)
def cancel(
    request_id: str, reviews: Reviews, benchmarks: Benchmarks, user: ActiveUser, request: Request
) -> ReviewRequestView:
    """Withdraw a request I sent."""
    pending = reviews.get_request(request_id)
    cancelled = benchmarks.cancel_review(pending.benchmark_id, user, request_id)
    return reviews.view(cancelled)
