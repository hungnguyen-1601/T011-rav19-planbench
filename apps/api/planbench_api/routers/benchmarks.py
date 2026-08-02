"""Benchmark endpoints: creation, approval workflow, execution, results."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from planbench_api.approval import Action, ApprovalRecord, BenchmarkState
from planbench_api.auth import ActiveUser
from planbench_api.dependencies import (
    get_benchmark_job_service,
    get_benchmark_service,
    get_review_service,
)
from planbench_api.report_markdown import render_report_markdown
from planbench_api.repositories import StoredBenchmark
from planbench_api.review import ReviewRequest, ReviewRequestView, ReviewStage, ReviewStatus
from planbench_api.review_service import ReviewService
from planbench_api.services import BenchmarkJobService, BenchmarkService
from planbench_benchmark import AlgorithmSpec, BenchmarkReport, BenchmarkSpec

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

Service = Annotated[BenchmarkService, Depends(get_benchmark_service)]
Jobs = Annotated[BenchmarkJobService, Depends(get_benchmark_job_service)]
Reviews = Annotated[ReviewService, Depends(get_review_service)]


class BenchmarkCreateRequest(BaseModel):
    name: str
    description: str = ""
    map_id: str
    scenario_id: str
    algorithms: list[AlgorithmSpec] = Field(min_length=1)
    seeds: list[int] = Field(min_length=1)


class CommentRequest(BaseModel):
    comment: str = ""


class BenchmarkResource(BaseModel):
    id: str
    spec: BenchmarkSpec
    map_id: str
    scenario_id: str
    state: BenchmarkState
    created_by: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    approvals: tuple[ApprovalRecord, ...] = ()
    report_artifact_uri: str | None = None
    #: Ownership and pending reviews, resolved for the calling member.
    #: The UI uses them to decide what to show; the backend decides what
    #: to allow, independently, on every request.
    owner_user_id: str = ""
    is_owner: bool = False
    #: Resolved to nicknames here rather than in the browser: the client
    #: has no way to turn a user id into a name, and asking it to would
    #: mean a lookup endpoint that leaks the member list.
    review_requests: tuple[ReviewRequestView, ...] = ()


class BenchmarkResultsResponse(BaseModel):
    benchmark: BenchmarkResource
    report: BenchmarkReport | None = None


def _resource(
    stored: StoredBenchmark,
    service: BenchmarkService | None = None,
    user=None,
    reviews: ReviewService | None = None,
) -> BenchmarkResource:
    return BenchmarkResource(
        id=stored.id,
        spec=stored.spec,
        map_id=stored.map_id,
        scenario_id=stored.scenario_id,
        state=stored.state,
        created_by=stored.created_by,
        created_at=stored.created_at,
        started_at=stored.started_at,
        finished_at=stored.finished_at,
        approvals=tuple(stored.approvals),
        report_artifact_uri=stored.report_artifact_uri,
        owner_user_id=stored.owner_user_id,
        is_owner=bool(service and user and service.is_owner(stored, user)),
        review_requests=(
            tuple(reviews.view(request) for request in reviews.for_benchmark(stored.id))
            if reviews
            else ()
        ),
    )


@router.get("", response_model=list[BenchmarkResource])
def list_benchmarks(
    service: Service, reviews: Reviews, user: ActiveUser
) -> list[BenchmarkResource]:
    """Every benchmark. Reading is not restricted — acting is.

    A shared leaderboard only means something if everyone can see the
    runs behind it, so visibility is deliberately wide and every
    mutating route re-checks ownership on its own.

    Review requests are deliberately *not* resolved here: the list view
    does not show them, and doing it per row would be a query per
    benchmark for something nobody reads.
    """
    return [_resource(stored, service, user) for stored in service.list()]


@router.post("", response_model=BenchmarkResource, status_code=status.HTTP_201_CREATED)
def create_benchmark(
    request: BenchmarkCreateRequest, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    return _resource(
        service.create(
            name=request.name,
            map_id=request.map_id,
            scenario_id=request.scenario_id,
            algorithms=request.algorithms,
            seeds=request.seeds,
            owner=user,
            description=request.description,
        ),
        service,
        user,
        reviews,
    )


@router.get("/{benchmark_id}", response_model=BenchmarkResource)
def get_benchmark(
    benchmark_id: str, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    return _resource(service.get(benchmark_id), service, user, reviews)


@router.post("/{benchmark_id}/submit", response_model=BenchmarkResource)
def submit(
    benchmark_id: str, request: CommentRequest, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    stored = service.transition(benchmark_id, Action.SUBMIT, user, request.comment)
    return _resource(stored, service, user, reviews)


@router.post("/{benchmark_id}/approve", response_model=BenchmarkResource)
def approve(
    benchmark_id: str, request: CommentRequest, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    """Clear the spec gate. Only the Approver named on a pending spec
    review may do this — the owner cannot clear their own gate; see
    ``admin_override_approve`` for the deliberate, logged exception.
    """
    stored = service.decide(
        benchmark_id, user, ReviewStage.SPEC, ReviewStatus.APPROVED, request.comment
    )
    return _resource(stored, service, user, reviews)


@router.post("/{benchmark_id}/reject", response_model=BenchmarkResource)
def reject(
    benchmark_id: str, request: CommentRequest, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    stored = service.decide(
        benchmark_id, user, ReviewStage.SPEC, ReviewStatus.REJECTED, request.comment
    )
    return _resource(stored, service, user, reviews)


@router.post("/{benchmark_id}/admin-override-approve", response_model=BenchmarkResource)
def admin_override_approve(
    benchmark_id: str, request: CommentRequest, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    """Clear the spec gate without an Approver.

    Admin only, and only on a deployment with
    ``PLANBENCH_ADMIN_OVERRIDE_ENABLED=true`` — see
    ``BenchmarkService.admin_override``. Recorded as its own action,
    never as ``approve``, so the audit trail never implies a second
    person reviewed it.
    """
    stored = service.admin_override(
        benchmark_id, user, Action.ADMIN_OVERRIDE_APPROVE, request.comment
    )
    return _resource(stored, service, user, reviews)


@router.post("/{benchmark_id}/admin-override-reject", response_model=BenchmarkResource)
def admin_override_reject(
    benchmark_id: str, request: CommentRequest, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    """The rejecting counterpart of ``admin_override_approve``."""
    stored = service.admin_override(
        benchmark_id, user, Action.ADMIN_OVERRIDE_REJECT, request.comment
    )
    return _resource(stored, service, user, reviews)


@router.post("/{benchmark_id}/cancel", response_model=BenchmarkResource)
def cancel(
    benchmark_id: str, request: CommentRequest, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    stored = service.transition(benchmark_id, Action.CANCEL, user, request.comment)
    return _resource(stored, service, user, reviews)


@router.post("/{benchmark_id}/run", response_model=BenchmarkResultsResponse)
def run_benchmark_endpoint(
    benchmark_id: str, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResultsResponse:
    """Run it. Requires APPROVED — an Approver's decision or an admin
    override, never the owner alone; see ``BenchmarkService.run``.
    """
    stored = service.run(benchmark_id, user)
    return BenchmarkResultsResponse(
        benchmark=_resource(stored, service, user, reviews), report=stored.report
    )


@router.post("/{benchmark_id}/accept-result", response_model=BenchmarkResource)
def accept_result(
    benchmark_id: str, request: CommentRequest, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    stored = service.decide(
        benchmark_id, user, ReviewStage.RESULT, ReviewStatus.APPROVED, request.comment
    )
    return _resource(stored, service, user, reviews)


@router.post("/{benchmark_id}/reject-result", response_model=BenchmarkResource)
def reject_result(
    benchmark_id: str, request: CommentRequest, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResource:
    stored = service.decide(
        benchmark_id, user, ReviewStage.RESULT, ReviewStatus.REJECTED, request.comment
    )
    return _resource(stored, service, user, reviews)


# -- asking someone to look -------------------------------------------


class ReviewRequestBody(BaseModel):
    """Send for review: who, which stage, and an optional note."""

    reviewer_nickname: str
    stage: ReviewStage
    comment: str = ""


@router.post(
    "/{benchmark_id}/review-requests",
    response_model=ReviewRequest,
    status_code=status.HTTP_201_CREATED,
)
def request_review(
    benchmark_id: str, payload: ReviewRequestBody, service: Service, user: ActiveUser
) -> ReviewRequest:
    return service.request_review(
        benchmark_id,
        user,
        stage=payload.stage,
        reviewer_nickname=payload.reviewer_nickname,
        comment=payload.comment,
    )


@router.get("/{benchmark_id}/review-requests", response_model=list[ReviewRequest])
def list_review_requests(
    benchmark_id: str, service: Service, reviews: Reviews, _: ActiveUser
) -> list[ReviewRequest]:
    service.get(benchmark_id)  # 404 if unknown
    return reviews.for_benchmark(benchmark_id)


@router.post("/{benchmark_id}/review-requests/{request_id}/cancel", response_model=ReviewRequest)
def cancel_review_request(
    benchmark_id: str, request_id: str, service: Service, user: ActiveUser
) -> ReviewRequest:
    return service.cancel_review(benchmark_id, user, request_id)


class JobStatus(BaseModel):
    """Progress of a background benchmark run."""

    id: str
    state: str
    progress: int
    total: int
    message: str
    error: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


@router.post(
    "/{benchmark_id}/run-async", response_model=JobStatus, status_code=status.HTTP_202_ACCEPTED
)
def run_async(benchmark_id: str, jobs: Jobs, user: ActiveUser) -> JobStatus:
    """Queue an approved benchmark on the bounded background worker.

    The approval gate is checked before queueing, so an unapproved
    benchmark is rejected here rather than inside the worker.
    """
    from planbench_api.errors import InvalidStateError

    try:
        job = jobs.start(benchmark_id, user)
    except ValueError as exc:  # already active
        raise InvalidStateError(str(exc)) from exc
    return _job_status(job)


@router.get("/{benchmark_id}/job", response_model=JobStatus)
def job_status(benchmark_id: str, jobs: Jobs, _: ActiveUser) -> JobStatus:
    from planbench_api.errors import NotFoundError

    job = jobs.status(benchmark_id)
    if job is None:
        raise NotFoundError("job", benchmark_id)
    return _job_status(job)


@router.post("/{benchmark_id}/job/cancel", response_model=JobStatus)
def cancel_job(benchmark_id: str, jobs: Jobs, _: ActiveUser) -> JobStatus:
    """Ask the worker to stop between episodes (cooperative cancel)."""
    from planbench_api.errors import InvalidStateError, NotFoundError

    job = jobs.status(benchmark_id)
    if job is None:
        raise NotFoundError("job", benchmark_id)
    if not jobs.cancel(benchmark_id):
        raise InvalidStateError(f"job {benchmark_id!r} already finished")
    return _job_status(jobs.status(benchmark_id))


def _job_status(job) -> JobStatus:  # noqa: ANN001 - worker.Job
    return JobStatus(
        id=job.id,
        state=job.state.value,
        progress=job.progress,
        total=job.total,
        message=job.message,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.get("/{benchmark_id}/results", response_model=BenchmarkResultsResponse)
def get_results(
    benchmark_id: str, service: Service, reviews: Reviews, user: ActiveUser
) -> BenchmarkResultsResponse:
    stored = service.get(benchmark_id)
    return BenchmarkResultsResponse(
        benchmark=_resource(stored, service, user, reviews), report=stored.report
    )


@router.get("/{benchmark_id}/report.md")
def get_report_markdown(benchmark_id: str, service: Service, _: ActiveUser) -> Response:
    from planbench_api.errors import InvalidStateError

    stored = service.get(benchmark_id)
    if stored.report is None:
        raise InvalidStateError(f"benchmark {benchmark_id!r} has no report yet; run it first")
    markdown = render_report_markdown(stored.spec.name, benchmark_id, stored.report)
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{benchmark_id}-report.md"'},
    )
