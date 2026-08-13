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

from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse
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
    get_decision_jobs,
    get_decision_run_service,
    get_map_root,
    get_task_profile_service,
)
from planbench_api.errors import DomainValidationError, NotFoundError
from planbench_api.worker import Job, JobQueue
from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS
from planbench_benchmark.selection import DEFAULT_SCOPE

router = APIRouter(tags=["decisions"])

Profiles = Annotated[TaskProfileService, Depends(get_task_profile_service)]
Candidates = Annotated[CandidateService, Depends(get_candidate_service)]
Runs = Annotated[DecisionRunService, Depends(get_decision_run_service)]
DecisionJobs = Annotated[JobQueue, Depends(get_decision_jobs)]
MapRoot = Annotated[Path, Depends(get_map_root)]


class TaskProfileResource(BaseModel):
    id: str
    environment: str
    owner_user_id: str | None
    created_at: str
    profile: dict[str, Any]


class DerivedProfileRequest(BaseModel):
    """A deployment identical to another except for its map (and missions).

    ``new_id`` is required rather than generated, and the server refuses
    it if it equals the base. Changing the map changes the world and
    ``episode_context_id`` does not hash the map (HĐ-3.1), so an
    in-place edit would let two worlds' episodes collide on one hash.
    Making the caller name the new world is how that stays visible.

    ``missions`` is optional and usually necessary: a start and goal that
    fit the old map are rarely on free floor in the new one, and the
    server checks before storing rather than letting every candidate
    return no_path.
    """

    base_task_profile_id: str = Field(min_length=1)
    new_id: str = Field(min_length=1)
    #: A map from the map store (`GET /maps`) — drawn in the editor,
    #: generated, or uploaded. It is written out as a map_server pair
    #: under `maps/custom/` so the engine can read it the usual way.
    map_id: str = Field(min_length=1)
    missions: list[dict[str, Any]] | None = None


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
    # The two human acts, kept apart (HĐ-14). `review_state` applies to
    # every run; `config_state` is `not_applicable` wherever there is no
    # card, which is what makes "approve a run that recommends nobody"
    # unreachable rather than merely refused.
    review_state: str
    reviewed_by: str | None
    reviewed_at: str | None
    config_state: str
    config_decided_by: str | None
    config_decided_at: str | None


class ReviewRequest(BaseModel):
    #: Optional, because "I read it and it says what it says" is a
    #: complete review. Required text would be answered with a full stop.
    comment: str = ""


class ConfigDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str = ""


class DecisionJobResource(BaseModel):
    """A queued sweep, and how far it has got.

    ``run_id`` is filled in only when the job succeeded — before that
    there is no run, and a field that carried a plausible id early would
    be pointing at nothing.
    """

    id: str
    state: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    #: Episode *runs* done and planned — one per (candidate, episode)
    #: pair, so thirty episodes across two candidates is sixty. Not the
    #: episode count: reporting that would make a two-candidate sweep
    #: look twice as far along as it is.
    #:
    #: ``total`` is 0 until the sweep reports its first pair. A
    #: denominator that arrives a second late is better than one that
    #: changes under the reader.
    progress: int
    total: int
    #: While running, the stack currently being simulated. On success,
    #: the stored run's id.
    message: str
    error: str | None
    run_id: str | None


class ReviewEventResource(BaseModel):
    sequence: int
    action: str
    actor_user_id: str | None
    username: str
    #: Both ends, because "approved" alone does not say what it replaced.
    previous_state: str
    new_state: str
    comment: str
    created_at: str


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


def _job(job: Job) -> DecisionJobResource:
    # `message` carries the stored run's id once the work finished, so a
    # client watching the job knows where to look without hunting the
    # list for something that appeared recently — "recent" is not an
    # identity, especially with a queue that runs one job at a time.
    return DecisionJobResource(
        id=job.id,
        state=str(job.state),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress=job.progress,
        total=job.total,
        message=job.message,
        error=job.error,
        run_id=job.message if job.state == "succeeded" else None,
    )


def _without_episode_tables(report: dict[str, Any] | None) -> dict[str, Any] | None:
    """The same report, minus each candidate's per-episode rows.

    Copied shallowly down to the candidate entries rather than mutated:
    the argument is the stored row's own dictionary, and dropping a key
    from it would delete the evidence from the repository to make a list
    page smaller.
    """
    if not report or "candidates" not in report:
        return report
    return {
        **report,
        "candidates": [
            {key: value for key, value in candidate.items() if key != "episodes"}
            if isinstance(candidate, dict)
            else candidate
            for candidate in report["candidates"]
        ],
    }


def _run(stored: StoredDecisionRun, *, with_episodes: bool = True) -> DecisionRunResource:
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
        report=stored.report if with_episodes else _without_episode_tables(stored.report),
        card=stored.card,
        review_state=stored.review_state,
        reviewed_by=stored.reviewed_by,
        reviewed_at=stored.reviewed_at,
        config_state=stored.config_state,
        config_decided_by=stored.config_decided_by,
        config_decided_at=stored.config_decided_at,
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


@router.post(
    "/task-profiles/derive",
    response_model=TaskProfileResource,
    status_code=status.HTTP_201_CREATED,
)
def derive_task_profile(
    request: DerivedProfileRequest, service: Profiles, user: CurrentUser
) -> TaskProfileResource:
    """Take an existing deployment and put a different map under it.

    **The only way a custom map reaches a comparison.** A profile names
    its map by path and the editor keeps grids in the database; this
    writes the chosen map out as a map_server pair and points the new
    profile at it.

    Refuses before storing anything when the missions do not fit the new
    map — a goal inside a shelf makes every candidate return no_path, and
    the comparison then reports a tie on a question none of them was
    asked, with every column reading a plausible 0.00.
    """
    return _profile(
        service.derive(
            base_task_profile_id=request.base_task_profile_id,
            new_id=request.new_id,
            map_id=request.map_id,
            missions=request.missions,
            owner_user_id=user.id,
        )
    )


@router.get("/task-profiles", response_model=list[TaskProfileResource])
def list_task_profiles(service: Profiles) -> list[TaskProfileResource]:
    return [_profile(stored) for stored in service.list()]


#: The deployment a form starts from. Registered **before**
#: ``/task-profiles/{profile_id}``: both are GET, so the first route
#: whose path matches wins, and the parametrised one would swallow
#: "template" and answer 404.
@router.get("/task-profiles/template", response_model=dict[str, Any])
def task_profile_template(map_root: MapRoot) -> dict[str, Any]:
    """The values a blank form opens with — read from the shipped profile.

    **Served rather than duplicated in the browser.** A hand-copied set
    of defaults in TypeScript would be a second statement of what a
    working deployment looks like, and the day somebody tunes
    ``open_hall_v2`` the form would quietly keep handing out the old
    numbers. This has one source and cannot drift from it.

    The hall rather than the warehouse because it is the small, symmetric
    instrument this project measures itself with: a form that opened on a
    300-episode warehouse would suggest that as the normal first run.
    """
    import yaml

    path = map_root / "profiles" / "open_hall_v2.yaml"
    if not path.is_file():
        raise NotFoundError("profile template", str(path))
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise NotFoundError("profile template", str(path))
    # The id is the one thing a template must not hand over: re-filing an
    # existing id with different content is refused (HĐ-3.1), so shipping
    # `open_hall_v2` here would make the first submit fail for a reason
    # the author did not choose.
    loaded["id"] = ""
    return loaded


@router.get("/task-profiles/{profile_id}", response_model=TaskProfileResource)
def get_task_profile(profile_id: str, service: Profiles) -> TaskProfileResource:
    return _profile(service.get(profile_id))


@router.post("/candidates", response_model=CandidateResource, status_code=status.HTTP_201_CREATED)
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


class LocalControllerConfig(BaseModel):
    """One named local-controller configuration and what it sets."""

    name: str
    params: dict[str, Any]


@router.get("/local-controllers", response_model=list[LocalControllerConfig])
def list_local_controllers() -> list[LocalControllerConfig]:
    """The named configurations a candidate may be registered with.

    **Served rather than copied into the client.** Registration already
    refuses a name that is not in this table, so a hand-maintained list
    in the browser would be a second statement of what the platform
    accepts — free to drift, and drifting silently until somebody's
    dropdown offers a configuration the server rejects.

    The parameters travel with the name because the name alone says
    nothing: `dwa_coarse` and `dwa_default` differ by 7x15 samples
    against 20x40, which is the entire reason a sampling choice is a
    *candidate* rather than a constant inside whichever script ran
    (HĐ-1.3).
    """
    return [
        LocalControllerConfig(name=name, params=dict(params))
        for name, params in sorted(LOCAL_CONTROLLER_CONFIGS.items())
    ]


@router.get("/candidates", response_model=list[CandidateResource])
def list_candidates(service: Candidates) -> list[CandidateResource]:
    return [_candidate(stored) for stored in service.list()]


@router.get("/candidates/{candidate_id}", response_model=CandidateResource)
def get_candidate(candidate_id: str, service: Candidates) -> CandidateResource:
    return _candidate(service.get(candidate_id))


@router.post("/decisions", response_model=DecisionRunResource, status_code=status.HTTP_201_CREATED)
def run_decision(request: DecisionRequest, service: Runs, user: CurrentUser) -> DecisionRunResource:
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


@router.post(
    "/decisions/jobs", response_model=DecisionJobResource, status_code=status.HTTP_202_ACCEPTED
)
def queue_decision(
    request: DecisionRequest, service: Runs, jobs: DecisionJobs, user: CurrentUser
) -> DecisionJobResource:
    """Queue a selection and hand back a job to watch. 202, not 201.

    202 because nothing has been created yet — the run appears in
    ``/decisions`` when the sweep finishes, and answering 201 with a job
    id would name a resource that does not exist.

    **The queue holds one job.** HĐ-7.4 forbids two evaluation runs on
    one machine at once: they pin the same cores and each becomes the
    other's background load, so G4 measures a machine that does not
    exist. A second request while one is running is queued, not run.

    ``POST /decisions`` still exists and still runs inside the request. A
    six-episode fixture finishes before a progress bar would appear, and
    making that caller poll would be ceremony.
    """
    if len({(spec.stack, spec.local_config) for spec in request.candidates}) < 2:
        raise DomainValidationError(
            "a selection needs at least two *distinct* candidates. The same configuration "
            "twice is the same candidate_id (HĐ-1.3), and a candidate cannot be its own rival"
        )
    return _job(
        service.submit(
            jobs=jobs,
            task_profile_id=request.task_profile_id,
            candidate_specs=[(spec.stack, spec.local_config) for spec in request.candidates],
            scope=request.scope,
            episodes=request.episodes,
            created_by=user.id,
            reuse_traces=request.reuse_traces,
        )
    )


@router.get("/decisions/jobs", response_model=list[DecisionJobResource])
def list_decision_jobs(jobs: DecisionJobs) -> list[DecisionJobResource]:
    return [_job(job) for job in jobs.list()]


@router.get("/decisions/jobs/{job_id}", response_model=DecisionJobResource)
def get_decision_job(job_id: str, jobs: DecisionJobs) -> DecisionJobResource:
    job = jobs.get(job_id)
    if job is None:
        raise NotFoundError("decision job", job_id)
    return _job(job)


@router.delete("/decisions/jobs/{job_id}", response_model=DecisionJobResource)
def cancel_decision_job(job_id: str, jobs: DecisionJobs, _: CurrentUser) -> DecisionJobResource:
    """Cancel a queued or running sweep.

    Episodes already written stay written, and that is the point rather
    than a leak: traces are keyed by content hash, so a later run of the
    same candidates on the same deployment reuses every one of them. A
    cancelled three-hour sweep costs nothing the second time.
    """
    jobs.cancel(job_id)
    job = jobs.get(job_id)
    if job is None:
        raise NotFoundError("decision job", job_id)
    return _job(job)


@router.get("/decisions", response_model=list[DecisionRunResource])
def list_decisions(
    service: Runs,
    task_profile_id: Annotated[str | None, Query()] = None,
    ranked: Annotated[bool | None, Query()] = None,
) -> list[DecisionRunResource]:
    """``?ranked=false`` is the day-one question: which runs could not be
    ranked, and at which gate did everybody fall out.

    The rows come back without their per-episode outcome tables. A
    warehouse run is 300 episodes across two candidates, and ten of them
    on one page is close to a megabyte of rows this page draws none of —
    the list shows who cleared the gates, and the detail page is where an
    episode is picked. Stripped rather than never stored: the report is
    written once by the engine and stays whole behind ``GET
    /decisions/{id}``.
    """
    return [
        _run(stored, with_episodes=False)
        for stored in service.list(task_profile_id=task_profile_id, ranked=ranked)
    ]


@router.get("/decisions/{run_id}", response_model=DecisionRunResource)
def get_decision(run_id: str, service: Runs) -> DecisionRunResource:
    return _run(service.get(run_id))


@router.post("/decisions/{run_id}/review", response_model=DecisionRunResource)
def review_decision(
    run_id: str, request: ReviewRequest, service: Runs, user: CurrentUser
) -> DecisionRunResource:
    """Record that somebody read this run's evidence.

    **Every run, including the ones that could not be ranked.** Four of
    the first five comparisons produced no card, and each still answered
    "who was eliminated where, after how many runs". A platform that only
    lets you sign off the runs that ranked is a platform where the other
    four quietly become artifacts nobody ever looked at — which is the
    outcome that made this a separate act from approval below.
    """
    return _run(
        service.review(
            run_id, actor_user_id=user.id, username=user.nickname, comment=request.comment
        )
    )


@router.post("/decisions/{run_id}/config-approval", response_model=DecisionRunResource)
def decide_config(
    run_id: str, request: ConfigDecisionRequest, service: Runs, user: CurrentUser
) -> DecisionRunResource:
    """Approve or reject this run's recommendation as a configuration.

    409 when the run has no card. That is not a technicality: approving a
    run that recommends nobody would turn "this was measured" into "this
    was endorsed", and the resulting ``approved_config.yaml`` would name
    no candidate at all.

    409 too when the caller started the run — separation of duties
    (HĐ-14). The person who chose the candidates, the deployment and the
    episode count is not an independent check on the answer.
    """
    return _run(
        service.decide_config(
            run_id,
            approve=request.decision == "approve",
            actor_user_id=user.id,
            username=user.nickname,
            comment=request.comment,
        )
    )


@router.get("/decisions/{run_id}/audit", response_model=list[ReviewEventResource])
def decision_audit(run_id: str, service: Runs) -> list[ReviewEventResource]:
    """The append-only trail, oldest first (HĐ-14).

    Ordered by ``sequence`` rather than by timestamp because two acts can
    share a clock reading, and "who decided first" is exactly the
    question an audit trail is asked.
    """
    return [
        ReviewEventResource(
            sequence=event.sequence,
            action=event.action,
            actor_user_id=event.actor_user_id,
            username=event.username,
            previous_state=event.previous_state,
            new_state=event.new_state,
            comment=event.comment,
            created_at=event.created_at,
        )
        for event in service.events(run_id)
    ]


@router.get("/decisions/{run_id}/traces/{candidate_id}/{episode_context_id}")
def get_trace(
    run_id: str, candidate_id: str, episode_context_id: str, service: Runs
) -> dict[str, Any]:
    """One episode's trajectory, with the map it was driven on.

    **The trace is the evidence.** One Parquet file per (candidate,
    episode) is the sole input the Metrics Engine has (HĐ-5), and every
    number on a Decision Card is derived from it. Until this endpoint
    existed, nothing could read one back: the platform computed gate
    verdicts from evidence nobody could look at, and asked to be
    believed.

    Not a response model, and that is deliberate: the payload is bulk
    telemetry — six parallel arrays and a packed occupancy grid — and
    validating 546 floats twice on the way out would buy nothing a
    schema check does not already give the writer.
    """
    return service.trace(run_id, candidate_id, episode_context_id)


@router.get("/decisions/{run_id}/approved_config.yaml", response_class=PlainTextResponse)
def approved_config(run_id: str, service: Runs) -> str:
    """The deployable configuration — approved runs only (HĐ-14).

    Served as text rather than JSON because it is a file somebody saves,
    and because the sim-only notice inside it should be the first thing
    read rather than a field in a viewer.
    """
    return service.approved_config(run_id)
