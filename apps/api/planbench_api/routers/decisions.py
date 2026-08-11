"""Deployments, candidates and selection runs over HTTP (Phase 6.2).

Three resources, one file, because they are one feature: a deployment is
the question, candidates are the answers on offer, and a run is the
evidence weighed between them.

**``POST /decisions`` returns 201 whether or not a card came out.** Fewer
than two candidates through the gates means no ΔU and no Decision Card,
and the gate table is then the whole deliverable — "who was eliminated
where, after how many runs" is the question HĐ-12 puts on a card in the
first place. Answering that with a 4xx would tell the caller their
request was wrong when the platform in fact answered it. The response
says ``ranked: false`` and carries the report; the client decides what to
show.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from planbench_api.auth import CurrentUser
from planbench_api.decision_service import (
    CandidateService,
    DecisionRunService,
    TaskProfileService,
)
from planbench_api.decisions import StoredCandidate, StoredDecisionRun, StoredTaskProfile
from planbench_api.dependencies import (
    get_candidate_service,
    get_decision_run_service,
    get_task_profile_service,
)
from planbench_api.errors import DomainValidationError
from planbench_benchmark.selection import DEFAULT_SCOPE

router = APIRouter(tags=["decisions"])

Profiles = Annotated[TaskProfileService, Depends(get_task_profile_service)]
Candidates = Annotated[CandidateService, Depends(get_candidate_service)]
Runs = Annotated[DecisionRunService, Depends(get_decision_run_service)]


class TaskProfileResource(BaseModel):
    id: str
    environment: str
    owner_user_id: str | None
    created_at: str
    profile: dict[str, Any]


class CandidateRegistration(BaseModel):
    """What a caller may choose. The **id is not on this list**.

    HĐ-1.3 makes ``candidate_id`` a hash of the configuration, so the
    server computes it. Accepting one would let two different stacks
    share an identity that every trace, pairing and ΔU keys on.
    """

    stack: str = Field(min_length=1, description="Registry stack id, e.g. 'astar+dwa'.")
    local_config: str = Field(default="dwa_coarse", description="Named local-controller config.")
    #: HĐ-1.6's declaration with its evidence log. Absent is allowed and
    #: is not the same as zero — the objectives layer charges silence.
    tuning: dict[str, Any] | None = None


class CandidateResource(BaseModel):
    candidate_id: str
    type: str
    stack_label: str
    registered_by: str | None
    created_at: str
    spec: dict[str, Any]
    tuning: dict[str, Any] | None


class CandidateSpec(BaseModel):
    stack: str = Field(min_length=1)
    local_config: str = "dwa_coarse"


class DecisionRequest(BaseModel):
    task_profile_id: str = Field(min_length=1)
    candidates: list[CandidateSpec] = Field(min_length=2)
    scope: str = DEFAULT_SCOPE
    #: Defaults to ``N_min`` from the profile (HĐ-7.1) — the episode
    #: count is a consequence of the declared collision risk, not a taste
    #: setting, so leaving it out is the normal case.
    episodes: int | None = Field(default=None, ge=1)
    reuse_traces: bool = True


class DecisionRunResource(BaseModel):
    id: str
    task_profile_id: str
    artifact_kind: str
    experiment_scope: str | None
    contracts_version: str
    created_at: str
    created_by: str | None
    #: ``False`` means the field could not be ranked. Not an error — the
    #: gate table below still says who was eliminated where.
    ranked: bool
    recommended_candidate_id: str | None
    status: str | None
    report: dict[str, Any]
    card: dict[str, Any] | None


def _profile(stored: StoredTaskProfile) -> TaskProfileResource:
    return TaskProfileResource(
        id=stored.id,
        environment=stored.environment,
        owner_user_id=stored.owner_user_id,
        created_at=stored.created_at,
        profile=stored.profile,
    )


def _candidate(stored: StoredCandidate) -> CandidateResource:
    return CandidateResource(
        candidate_id=stored.candidate_id,
        type=stored.type,
        stack_label=stored.stack_label,
        registered_by=stored.registered_by,
        created_at=stored.created_at,
        spec=stored.spec,
        tuning=stored.tuning,
    )


def _run(stored: StoredDecisionRun) -> DecisionRunResource:
    return DecisionRunResource(
        id=stored.id,
        task_profile_id=stored.task_profile_id,
        artifact_kind=stored.artifact_kind,
        experiment_scope=stored.experiment_scope,
        contracts_version=stored.contracts_version,
        created_at=stored.created_at,
        created_by=stored.created_by,
        ranked=stored.ranked,
        recommended_candidate_id=stored.recommended_candidate_id,
        status=stored.status,
        report=stored.report,
        card=stored.card,
    )


@router.post(
    "/task-profiles",
    response_model=TaskProfileResource,
    status_code=status.HTTP_201_CREATED,
)
def create_task_profile(
    payload: dict[str, Any], service: Profiles, user: CurrentUser
) -> TaskProfileResource:
    return _profile(service.create(payload, owner_user_id=user.id))


@router.get("/task-profiles", response_model=list[TaskProfileResource])
def list_task_profiles(service: Profiles) -> list[TaskProfileResource]:
    return [_profile(stored) for stored in service.list()]


@router.get("/task-profiles/{profile_id}", response_model=TaskProfileResource)
def get_task_profile(profile_id: str, service: Profiles) -> TaskProfileResource:
    return _profile(service.get(profile_id))


@router.post(
    "/candidates", response_model=CandidateResource, status_code=status.HTTP_201_CREATED
)
def register_candidate(
    registration: CandidateRegistration, service: Candidates, user: CurrentUser
) -> CandidateResource:
    return _candidate(
        service.register(
            stack=registration.stack,
            local_config=registration.local_config,
            registered_by=user.id,
            tuning=registration.tuning,
        )
    )


@router.get("/candidates", response_model=list[CandidateResource])
def list_candidates(service: Candidates) -> list[CandidateResource]:
    return [_candidate(stored) for stored in service.list()]


@router.get("/candidates/{candidate_id}", response_model=CandidateResource)
def get_candidate(candidate_id: str, service: Candidates) -> CandidateResource:
    return _candidate(service.get(candidate_id))


@router.post(
    "/decisions", response_model=DecisionRunResource, status_code=status.HTTP_201_CREATED
)
def run_decision(
    request: DecisionRequest, service: Runs, user: CurrentUser
) -> DecisionRunResource:
    """Run a selection and store the result, ranked or not.

    Synchronous on purpose at this size. The episode count comes from the
    declared collision risk, so a caller who wants a 300-episode
    warehouse run is asking for hours of simulation and should be told
    that by the clock rather than by a job id that hides it — and the
    existing worker queue is bounded and shared with benchmark runs, so
    parking a three-hour selection in it would starve them. Moving this
    behind the queue is a deliberate change with its own cancellation
    story, not a default.
    """
    if len({(spec.stack, spec.local_config) for spec in request.candidates}) < 2:
        raise DomainValidationError(
            "a selection needs at least two *distinct* candidates. The same configuration "
            "twice is the same candidate_id (HĐ-1.3), and a candidate cannot be its own rival"
        )
    return _run(
        service.run(
            task_profile_id=request.task_profile_id,
            candidate_specs=[(spec.stack, spec.local_config) for spec in request.candidates],
            scope=request.scope,
            episodes=request.episodes,
            created_by=user.id,
            reuse_traces=request.reuse_traces,
        )
    )


@router.get("/decisions", response_model=list[DecisionRunResource])
def list_decisions(
    service: Runs,
    task_profile_id: Annotated[str | None, Query()] = None,
    ranked: Annotated[bool | None, Query()] = None,
) -> list[DecisionRunResource]:
    """``?ranked=false`` is the day-one question: which runs could not be
    ranked, and at which gate did everybody fall out."""
    return [_run(stored) for stored in service.list(task_profile_id=task_profile_id, ranked=ranked)]


@router.get("/decisions/{run_id}", response_model=DecisionRunResource)
def get_decision(run_id: str, service: Runs) -> DecisionRunResource:
    return _run(service.get(run_id))
