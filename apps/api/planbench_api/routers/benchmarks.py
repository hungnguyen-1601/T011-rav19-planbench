"""Benchmark endpoints: creation, approval workflow, execution, results."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from planbench_api.approval import Action, ApprovalRecord, BenchmarkState, Role
from planbench_api.auth import User, require_roles
from planbench_api.dependencies import get_benchmark_job_service, get_benchmark_service
from planbench_api.repositories import StoredBenchmark
from planbench_api.services import BenchmarkJobService, BenchmarkService
from planbench_benchmark import AlgorithmSpec, BenchmarkReport, BenchmarkSpec

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

Service = Annotated[BenchmarkService, Depends(get_benchmark_service)]
Jobs = Annotated[BenchmarkJobService, Depends(get_benchmark_job_service)]
Operator = Annotated[User, Depends(require_roles(Role.OPERATOR))]
Reviewer = Annotated[User, Depends(require_roles(Role.REVIEWER))]
AnyUser = Annotated[User, Depends(require_roles(Role.OPERATOR, Role.REVIEWER))]


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


class BenchmarkResultsResponse(BaseModel):
    benchmark: BenchmarkResource
    report: BenchmarkReport | None = None


def _resource(stored: StoredBenchmark) -> BenchmarkResource:
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
    )


@router.get("", response_model=list[BenchmarkResource])
def list_benchmarks(service: Service, _: AnyUser) -> list[BenchmarkResource]:
    return [_resource(stored) for stored in service.list()]


@router.post("", response_model=BenchmarkResource, status_code=status.HTTP_201_CREATED)
def create_benchmark(
    request: BenchmarkCreateRequest, service: Service, user: Operator
) -> BenchmarkResource:
    return _resource(
        service.create(
            name=request.name,
            map_id=request.map_id,
            scenario_id=request.scenario_id,
            algorithms=request.algorithms,
            seeds=request.seeds,
            created_by=user.username,
            description=request.description,
        )
    )


@router.get("/{benchmark_id}", response_model=BenchmarkResource)
def get_benchmark(benchmark_id: str, service: Service, _: AnyUser) -> BenchmarkResource:
    return _resource(service.get(benchmark_id))


@router.post("/{benchmark_id}/submit", response_model=BenchmarkResource)
def submit(
    benchmark_id: str, request: CommentRequest, service: Service, user: Operator
) -> BenchmarkResource:
    return _resource(service.transition(benchmark_id, Action.SUBMIT, user, request.comment))


@router.post("/{benchmark_id}/approve", response_model=BenchmarkResource)
def approve(
    benchmark_id: str, request: CommentRequest, service: Service, user: Reviewer
) -> BenchmarkResource:
    return _resource(service.transition(benchmark_id, Action.APPROVE, user, request.comment))


@router.post("/{benchmark_id}/reject", response_model=BenchmarkResource)
def reject(
    benchmark_id: str, request: CommentRequest, service: Service, user: Reviewer
) -> BenchmarkResource:
    return _resource(service.transition(benchmark_id, Action.REJECT, user, request.comment))


@router.post("/{benchmark_id}/cancel", response_model=BenchmarkResource)
def cancel(
    benchmark_id: str, request: CommentRequest, service: Service, user: Operator
) -> BenchmarkResource:
    return _resource(service.transition(benchmark_id, Action.CANCEL, user, request.comment))


@router.post("/{benchmark_id}/run", response_model=BenchmarkResultsResponse)
def run_benchmark_endpoint(
    benchmark_id: str, service: Service, user: Operator
) -> BenchmarkResultsResponse:
    """Execute an approved benchmark synchronously (background worker: M5)."""
    stored = service.run(benchmark_id, user)
    return BenchmarkResultsResponse(benchmark=_resource(stored), report=stored.report)


@router.post("/{benchmark_id}/accept-result", response_model=BenchmarkResource)
def accept_result(
    benchmark_id: str, request: CommentRequest, service: Service, user: Reviewer
) -> BenchmarkResource:
    return _resource(service.transition(benchmark_id, Action.ACCEPT_RESULT, user, request.comment))


@router.post("/{benchmark_id}/reject-result", response_model=BenchmarkResource)
def reject_result(
    benchmark_id: str, request: CommentRequest, service: Service, user: Reviewer
) -> BenchmarkResource:
    return _resource(service.transition(benchmark_id, Action.REJECT_RESULT, user, request.comment))


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
def run_async(benchmark_id: str, jobs: Jobs, user: Operator) -> JobStatus:
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
def job_status(benchmark_id: str, jobs: Jobs, _: AnyUser) -> JobStatus:
    from planbench_api.errors import NotFoundError

    job = jobs.status(benchmark_id)
    if job is None:
        raise NotFoundError("job", benchmark_id)
    return _job_status(job)


@router.post("/{benchmark_id}/job/cancel", response_model=JobStatus)
def cancel_job(benchmark_id: str, jobs: Jobs, _: Operator) -> JobStatus:
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
def get_results(benchmark_id: str, service: Service, _: AnyUser) -> BenchmarkResultsResponse:
    stored = service.get(benchmark_id)
    return BenchmarkResultsResponse(benchmark=_resource(stored), report=stored.report)
