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

import logging
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from planbench_agent.advisor import advise_with_model
from planbench_agent.critique import critique_with_model
from planbench_agent.paper import (
    extract_from_paper,
    read_upload,
    selectable_stacks,
)
from planbench_agent.plugin_author import author_plugin
from planbench_api.auth import CurrentUser
from planbench_api.decision_service import (
    CandidateService,
    DecisionRunService,
    TaskProfileService,
    TestBenchService,
)
from planbench_api.decisions import StoredCandidate, StoredDecisionRun, StoredTaskProfile
from planbench_api.dependencies import (
    get_agent_service,
    get_candidate_service,
    get_decision_jobs,
    get_decision_run_service,
    get_map_root,
    get_task_profile_service,
    get_test_bench_service,
)
from planbench_api.errors import DomainValidationError, NotFoundError
from planbench_api.worker import Job, JobQueue
from planbench_benchmark.candidates import offered_controller_configs
from planbench_benchmark.outcome import OUTCOME_CODES, build_outcome, outcome_advice
from planbench_benchmark.preflight import PREFLIGHT_CODES, build_draft, preflight
from planbench_benchmark.recommendation import (
    RECOMMENDATION_CODES,
    recommend_from_history,
    recommendation_source,
)
from planbench_benchmark.reproduction import (
    REPRODUCTION_CODES,
    build_comparison,
    reproduction_advice,
)
from planbench_benchmark.selection import DEFAULT_SCOPE
from planbench_decision.gate_advice import GATE_ADVICE_CODES, build_diagnosis, gate_advice
from planbench_decision.report_advice import (
    REPORT_ADVICE_CODES,
    build_reporting_source,
    report_advice,
)
from planbench_decision.self_check import RULE_CODES, critique
from planbench_metrics.trace_review import TRACE_REVIEW_CODES, trace_advice

logger = logging.getLogger("planbench.api")

#: A paper that does not fit is a paper the model reads the tail of, and
#: the Setup section is usually near the front. The cap is on the text
#: after extraction, so it bounds the model's input rather than the
#: upload.
MAX_PAPER_CHARS = 60_000

#: Well under what a PDF of a conference paper runs to, and small enough
#: that a mis-picked file fails at the door rather than after a minute of
#: parsing.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

router = APIRouter(tags=["decisions"])

#: Which language an export is rendered in. A `Literal` rather than a
#: free string so an unknown value is a 422 from FastAPI's own
#: validation: a caller asking for a language nobody built should hear
#: about it, rather than receive a document in a different one and take
#: that for the only one available.
ExportLocale = Annotated[
    Literal["en", "vi"],
    Query(description="Language of the exported document."),
]
#: English, so a client written before this parameter existed keeps
#: receiving exactly the document it received before.
DEFAULT_EXPORT_LOCALE: Literal["en", "vi"] = "en"

Profiles = Annotated[TaskProfileService, Depends(get_task_profile_service)]
Candidates = Annotated[CandidateService, Depends(get_candidate_service)]
Runs = Annotated[DecisionRunService, Depends(get_decision_run_service)]
DecisionJobs = Annotated[JobQueue, Depends(get_decision_jobs)]
MapRoot = Annotated[Path, Depends(get_map_root)]
TestBench = Annotated[TestBenchService, Depends(get_test_bench_service)]


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
    #: Either a named config or explicit params — never both. The second
    #: door exists for the paper flow: a paper states values, not a name
    #: this platform invented, and forcing it through a name meant the
    #: id the reading printed could never actually be registered.
    local_config: str = Field(default="", description="Named local-controller config.")
    params: dict[str, Any] | None = Field(
        default=None, description="Explicit controller parameters, from a paper reading."
    )
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


class FindingResource(BaseModel):
    """One objection, with the field a reader can check it against."""

    code: str
    severity: str
    kind: str
    claim: str
    ground: str
    field_path: str
    suggested_check: str
    #: ``rule`` reproduces exactly; ``model`` does not. A reader deciding
    #: how much weight to give an objection needs to know which it is.
    source: str = "rule"
    rank: int | None = None


class AdviceResource(BaseModel):
    """One thing to do, and one thing not to.

    ``do_not`` is the field that earns the shape. Every gate in this
    platform has a remedy that makes the symptom vanish without making
    the conclusion true — loosen the threshold, add the observation token
    the deployment does not really have — and a reader told only "this
    failed" is being invited to find it.
    """

    code: str
    kind: str
    severity: str
    claim: str
    ground: str
    field_path: str
    do: str
    do_not: str = ""
    subject: str = ""
    #: ``rule`` is deterministic; ``model`` is the LLM's addition, held
    #: to the same citation standard and scored separately.
    source: str = "rule"


class PreflightPlan(BaseModel):
    """What the run would cost, in the units a person cancels over."""

    episodes_requested: int | None
    episodes_per_candidate: int
    seed_count: int
    n_min_required: int
    episode_runs_total: int


class PreflightResource(BaseModel):
    """Advice about a comparison nobody has run yet.

    ``rules_applied`` is here for the same reason it is on the critique:
    an empty ``advice`` list has to read as "twelve rules looked and none
    objected" rather than "nothing was checked". Without it, the most
    valuable answer this endpoint gives — silence on a correct plan — is
    indistinguishable from a broken feature.
    """

    task_profile_id: str
    scope: str
    plan: PreflightPlan
    rules_applied: int
    advice: list[AdviceResource]
    blocking: int
    material: int
    disclosure: int
    #: One paragraph the model wrote for the reader; empty when the
    #: model did not run or declined.
    summary: str = ""
    #: Model additions dropped for citing a field that does not resolve.
    #: Published, not buried: it is how a reader tells a model that added
    #: judgement from one that added noise.
    fabricated: int = 0
    refused: str = ""


class AdviceListResource(BaseModel):
    """A list of advice, with the count of rules behind it.

    ``rules_applied`` is not decoration. An empty list has to read as
    "ten rules looked and none objected" rather than "nothing ran", and
    without the count those two are the same response.
    """

    rules_applied: int
    advice: list[AdviceResource]
    blocking: int
    material: int
    disclosure: int
    #: One paragraph the model wrote for the reader; empty when the
    #: model did not run or declined.
    summary: str = ""
    #: Model additions dropped for citing a field that does not resolve.
    #: Published, not buried — it is how a reader tells a model that
    #: added judgement from one that added noise.
    fabricated: int = 0
    refused: str = ""


class RecommendationCaseResource(BaseModel):
    """One mission's verdict inside one run — the 'in which cases' row.

    ``ci95`` is null exactly when ``status`` is ``INSUFFICIENT_EPISODES``:
    a group too small to bootstrap is described, never concluded from,
    and shipping a null instead of a made-up interval is the description.
    """

    run_id: str
    mission_id: str
    n_pairs: int
    delta_mean: float
    delta_median: float
    ci95: tuple[float, float] | None
    status: str
    winner_stack: str | None
    winner_candidate_id: str | None


class RecommendationResource(BaseModel):
    """Which algorithm this deployment should use, argued from stored runs.

    ``evidence_tier`` says where the answer stands: 1 means measured on
    this very profile, 3 means no comparable evidence exists and the
    advice is "run this comparison" rather than "adopt this stack".
    Tier 2 — transfer from a similar environment — is deliberately not
    produced yet; a field that names its own gap is how a reader knows
    the gap exists rather than assuming it was covered.
    """

    task_profile_id: str
    evidence_tier: int
    runs_considered: list[str]
    cases: list[RecommendationCaseResource]
    rules_applied: int
    advice: list[AdviceResource]
    blocking: int
    material: int
    disclosure: int
    summary: str = ""
    fabricated: int = 0
    refused: str = ""


class ReproductionRequest(BaseModel):
    """A paper reading and a registered candidate, in one call.

    Both in the request because the platform stores neither the paper nor
    the reading — ``POST /candidates/from-paper`` returns a draft and
    writes nothing, deliberately. The cost is that this diff cannot be
    re-run later without the document again; the alternative was becoming
    a place papers live.
    """

    candidate_id: str = Field(min_length=1)
    extraction: dict[str, Any]
    task_profile_id: str = ""


class ReproductionResource(AdviceListResource):
    """The advice, and the field-by-field table it was computed from."""

    candidate_id: str
    parameters: list[dict[str, Any]]


class TraceReviewResource(AdviceListResource):
    """Why one episode ended the way it did, from its own trace."""

    candidate_id: str
    episode_context_id: str
    #: The numbers every piece of advice cites, published beside it so a
    #: reader can check a citation without re-opening the Parquet.
    summary: dict[str, Any]


class PluginRequest(BaseModel):
    """Text of a paper whose method this platform does not have."""

    text: str = Field(min_length=1, max_length=MAX_PAPER_CHARS)


class PluginDraftResource(BaseModel):
    """A plugin bundle proposal, with the validator's verdict on it.

    ``accepted`` is the deterministic validator's word, never the
    model's: the Algorithm Host takes exactly one shape, and an answer
    out of shape comes back rejected with the errors named — not
    repaired, because a repaired draft teaches the model that malformed
    output works. Nothing is stored; the bundle is text for a person to
    review, finish and test.
    """

    manifest: dict[str, Any]
    files: dict[str, str]
    errors: list[str]
    notes: list[str]
    summary: str
    refused: str
    accepted: bool
    provider: str
    model: str
    deterministic: bool


class CritiqueResource(BaseModel):
    """Every objection raised against one run, and what was discarded.

    ``rules_applied`` is here so an empty ``findings`` list reads as "the
    rules ran and found nothing" rather than "no rules ran". The counts
    are split by severity, and separately by kind, because an omission
    that nobody noticed is a different failure from a contradiction
    nobody resolved — and published work on planted-error detection finds
    automated reviewers much weaker on the first.

    The model fields are the honesty budget. ``fabricated`` counts
    objections the model made up and had taken away; ``refused`` says why
    there is no prose when there is none; ``deterministic`` says whether
    asking again would give this same answer.
    """

    run_id: str
    rules_applied: int
    findings: list[FindingResource]
    blocking: int
    material: int
    disclosure: int
    omissions: int
    from_model: int = 0
    summary: str = ""
    fabricated: int = 0
    refused: str = ""
    provider: str = ""
    model: str = ""
    deterministic: bool = True


class PaperRequest(BaseModel):
    """Text of a paper, pasted.

    The sibling of the upload route rather than its predecessor: a reader
    quoting one Setup paragraph should not have to make a file first, and
    a scanned PDF that no extractor can read still has a person who can
    retype the two lines that matter.
    """

    text: str = Field(min_length=1, max_length=MAX_PAPER_CHARS)


class ExtractedParameterResource(BaseModel):
    name: str
    value: Any
    #: The sentence in the source this value came from. Verified against
    #: the text before it is shown, never trusted.
    quote: str
    note: str = ""


class PaperExtractionResource(BaseModel):
    """A candidate draft recovered from a paper, and what it could not do.

    Nothing is registered. ``candidate_id`` says the draft *would*
    register, which is different from having registered it — the person
    reading still has to agree that this is what the paper said.
    """

    stack: str
    params: dict[str, Any]
    parameters: list[ExtractedParameterResource]
    #: Parameters the paper never stated. These are the usual reason a
    #: reproduction fails, so they are output rather than silently
    #: defaulted.
    assumptions: list[str]
    #: What the paper describes that this platform cannot express.
    not_representable: list[str]
    claimed_conditions: str
    #: Values whose quote was not in the source, dropped and counted.
    unquoted: int
    refused: str
    candidate_id: str
    errors: list[str]
    provider: str
    model: str
    deterministic: bool
    #: What the model was allowed to choose between, so a reader can see
    #: the shortlist rather than infer it from the answer.
    offerable_stacks: list[str]
    #: How much of the document the model actually saw, against how much
    #: there was. Equal is the ordinary case; unequal means the tail was
    #: cut, and a reading of two thirds of a paper must not be presented
    #: as a reading of the paper.
    chars_read: int = 0
    chars_total: int = 0


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


@router.post("/task-profiles/validate", status_code=status.HTTP_204_NO_CONTENT)
def validate_task_profile(payload: dict[str, Any], service: Profiles, _: CurrentUser) -> None:
    """Run the check filing runs, without filing anything.

    **Why this exists rather than a copy of the rules in the browser.**
    The form has thirty inputs and a block of traffic; a refusal that
    arrives only on submit makes the author guess which of them the
    server disliked. The tempting fix is to check the easy rules in
    TypeScript, and that is exactly the thing the form is built not to
    do — a second opinion in the browser is free to disagree with the one
    that actually decides. So the verdict comes from here, from
    ``TaskProfile`` itself.

    **Same refusal shape as ``create``**: an invalid document raises
    ``DomainValidationError`` and leaves as a 422 carrying the same
    per-field addresses, so the form has one error path rather than two.
    A valid one returns 204 and no body — there is nothing to say about a
    document that is merely legal.

    **It reads the document only.** Nothing is stored and nothing is
    looked up, so a 204 is not a promise that filing will succeed: an id
    already on file with different content is refused by ``create``
    (HĐ-3.1), and that refusal cannot appear until then.

    Signed in, like every other POST here. Nothing is written and nothing
    is owned, but this runs the same code path ``create`` does, and a
    door to it that needs no account is a door that drifts.
    """
    service.validate(payload)


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


class ProfileDeleted(BaseModel):
    id: str
    #: How many stored runs went with it. Reported rather than assumed —
    #: a caller who confirmed "delete 7 runs" deserves to be told 7 were
    #: deleted, not to infer it from a 200.
    deleted_runs: int


@router.delete("/task-profiles/{profile_id}", response_model=ProfileDeleted)
def delete_task_profile(
    profile_id: str,
    service: Profiles,
    _: CurrentUser,
    delete_runs: bool = Query(
        default=False,
        description="Also delete every stored run filed against this deployment.",
    ),
) -> ProfileDeleted:
    """Delete a deployment, and say what went with it.

    **A deployment nobody ran deletes straight away**: it is a
    description, and deleting it destroys nothing that was measured.

    **A deployment with runs is refused** until the caller passes
    ``delete_runs``. Every run is a statement *about* this deployment —
    which is why the foreign key is ``ON DELETE RESTRICT`` and not a
    cascade — so removing it turns measurements into records of nothing,
    possibly including a configuration somebody approved.

    The refusal is a 409 carrying the counts, so the dialog can ask
    "delete seven runs, two of them approved?" instead of "are you
    sure?". Two clicks, and the second one names its own consequence.
    """
    return ProfileDeleted(
        id=profile_id, deleted_runs=service.delete(profile_id, delete_runs=delete_runs)
    )


class TestBenchRequest(BaseModel):
    """One episode of a deployment, to watch rather than to measure.

    ``seed`` is named rather than drawn. Two runs of the test bench with
    the same seed are the same episode down to the obstacle trajectories
    and the noise draws, which is what makes "watch it again, slower"
    mean anything — and a seed picked by the server would make the one
    thing worth re-watching irreproducible.
    """

    mission_id: str = Field(min_length=1)
    seed: int = Field(default=0, ge=0)
    stack: str = Field(min_length=1, description="Registry stack id, e.g. 'astar+dwa'.")
    local_config: str = Field(default="dwa_coarse")


class TestBenchResource(BaseModel):
    #: What to run and stream. The old `/simulations` endpoints and the
    #: existing WebSocket take it from here unchanged.
    simulation_id: str
    scenario_id: str
    map_id: str
    #: The real HĐ-3.1 id of the conditions assembled. Shown because it
    #: is the honest answer to "is this the same episode the comparison
    #: will run" — it is, and this is the identity that says so.
    episode_context_id: str
    scenario: dict[str, Any]


@router.post(
    "/task-profiles/{profile_id}/test-bench",
    response_model=TestBenchResource,
    status_code=status.HTTP_201_CREATED,
)
def stage_test_bench_episode(
    profile_id: str, request: TestBenchRequest, service: TestBench
) -> TestBenchResource:
    """Assemble one episode of this deployment and hand back a simulation.

    **Not a measurement, and the response says which parts are real.**
    The conditions are genuine — same ``scenario_for``, same registry
    entry, same episode seed as :func:`run_contract_episode` — so what
    you watch is what the comparison will run. What is *not* produced is
    an HĐ-5 trace: nothing here reaches the Metrics Engine, no gate sees
    it, no card counts it. That distinction is the whole reason this is
    allowed to run outside the context-outer order (HĐ-3.2) and beside a
    live evaluation (HĐ-7.4).

    Staging is idempotent in what it stores: the same deployment and seed
    reuse the map row and the scenario row rather than filing new ones,
    because the scenario's name *is* the episode context id.
    """
    staged = service.stage(
        task_profile_id=profile_id,
        mission_id=request.mission_id,
        seed=request.seed,
        stack=request.stack,
        local_config=request.local_config,
    )
    return TestBenchResource(
        simulation_id=staged.simulation_id,
        scenario_id=staged.scenario_id,
        map_id=staged.map_id,
        episode_context_id=staged.episode_context_id,
        scenario=staged.scenario,
    )


@router.post("/candidates", response_model=CandidateResource, status_code=status.HTTP_201_CREATED)
def register_candidate(
    registration: CandidateRegistration, service: Candidates, user: CurrentUser
) -> CandidateResource:
    # An empty registration defaults to the named path with dwa_coarse,
    # which is what every existing caller sends implicitly.
    local_config = registration.local_config
    if registration.params is None and not local_config:
        local_config = "dwa_coarse"
    return _candidate(
        service.register(
            stack=registration.stack,
            local_config=local_config,
            params=registration.params,
            registered_by=user.id,
            tuning=registration.tuning,
        )
    )


class LocalControllerConfig(BaseModel):
    """One named configuration, and the controller it configures."""

    #: Which local controller this belongs to. Sent because a
    #: configuration only means anything for its own controller —
    #: ``velocity_samples`` is a DWA idea, and offering it while a PPO
    #: policy is selected would be offering a knob with nothing behind
    #: it.
    controller: str
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

    **Only configurations a registration would accept appear.** A
    controller whose every stack has been withdrawn still has entries in
    ``CONTROLLER_CONFIGS`` — they are kept so past runs stay readable —
    but offering them here would put names in a dropdown that
    ``POST /candidates`` answers 422 to, which is the drift this endpoint
    exists to prevent rather than to cause.

    The parameters travel with the name because the name alone says
    nothing: `dwa_coarse` and `dwa_default` differ by 7x15 samples
    against 20x40, which is the entire reason a sampling choice is a
    *candidate* rather than a constant inside whichever script ran
    (HĐ-1.3).
    """
    return [
        LocalControllerConfig(controller=controller, name=name, params=dict(params))
        for controller, configs in sorted(offered_controller_configs().items())
        for name, params in sorted(configs.items())
    ]


@router.get("/candidates", response_model=list[CandidateResource])
def list_candidates(service: Candidates) -> list[CandidateResource]:
    return [_candidate(stored) for stored in service.list()]


@router.get("/candidates/{candidate_id}", response_model=CandidateResource)
def get_candidate(candidate_id: str, service: Candidates) -> CandidateResource:
    return _candidate(service.get(candidate_id))


def _advice_counts(items: list[AdviceResource], rules: int) -> dict[str, Any]:
    """Counts derived beside the list, never passed in — the
    `_critique_resource` precedent, for the same reason: a caller that
    supplies its own counts can supply wrong ones."""
    return {
        "rules_applied": rules,
        "advice": items,
        "blocking": sum(1 for a in items if a.severity == "blocking"),
        "material": sum(1 for a in items if a.severity == "material"),
        "disclosure": sum(1 for a in items if a.severity == "disclosure"),
    }


@router.get("/decisions/{run_id}/advice", response_model=AdviceListResource)
def decision_advice(
    run_id: str,
    service: Runs,
    profiles: Profiles,
    request: Request,
    user: CurrentUser,
    use_model: Annotated[bool, Query()] = False,
) -> AdviceListResource:
    """What to do about each gate this run did not clear.

    The gate table already says *which* gate failed. This says what the
    failure means, what the legitimate next step is, and — the part that
    earns the endpoint — which remedy the contract bars. Every gate here
    has one that makes the symptom vanish without making the conclusion
    true, and it is one field away in a form the same person may edit.

    Read-only, like every advisory route. It re-decides nothing: the
    verdicts are read from the stored report, never recomputed, because a
    module that could disagree with a gate would be a gate with no
    contract behind it.
    """
    stored = service.get(run_id)
    report = stored.report if isinstance(stored.report, dict) else dict(stored.report or {})
    profile: dict[str, Any] = {}
    try:
        profile = profiles.load(report.get("identity", {}).get("task_profile_id", "")).model_dump(
            mode="json"
        )
    except (NotFoundError, DomainValidationError):
        # Narrow on purpose. The thresholds live on the profile and the
        # observations live on the report, so a deployment that has since
        # been deleted costs the advice its numbers rather than its
        # existence — that degradation is wanted. A bare `except
        # Exception` here would give the same quiet fallback to a typo in
        # this function, and the advice would come back numberless with
        # nothing anywhere saying why.
        logger.warning("advice: task profile unavailable for run %s", run_id)
        profile = {}
    diagnosis = build_diagnosis(report, profile)
    found = gate_advice(diagnosis)
    if not use_model:
        items = [AdviceResource(**a.model_dump()) for a in found]
        return AdviceListResource(**_advice_counts(items, len(GATE_ADVICE_CODES)))

    # The model may rank and extend, never overrule: the rules' advice is
    # the floor, additions must cite a field that exists, and a fabricated
    # citation is dropped and counted where the reader can see the count.
    agent = get_agent_service(request, user)
    advised = advise_with_model("diagnosis", diagnosis, found, agent.provider)
    items = [
        AdviceResource(
            code=a.code,
            kind=a.kind,
            severity=a.severity,
            claim=a.claim,
            ground=a.ground,
            field_path=a.field_path,
            do=a.do,
            do_not=a.do_not,
            subject=a.subject,
            source=a.source,
        )
        for a in advised.advice
    ]
    return AdviceListResource(
        **_advice_counts(items, len(GATE_ADVICE_CODES)),
        summary=advised.summary,
        fabricated=advised.fabricated,
        refused=advised.refused,
    )


@router.post("/candidates/{candidate_id}/reproduction", response_model=ReproductionResource)
def candidate_reproduction(
    candidate_id: str,
    payload: ReproductionRequest,
    candidates: Candidates,
    profiles: Profiles,
    user: CurrentUser,
) -> ReproductionResource:
    """Why this candidate's numbers will differ from the paper's.

    **Nothing is stored, and the request shape follows from that.** The
    reading is passed in rather than looked up, because the platform
    keeps no copy of a paper. The cost is real and worth naming: two
    months from now this diff cannot be re-run without the document
    again. The alternative was a document store, with everything that
    implies about retention and provenance.

    The finding that matters most is the quiet one. A paper states two or
    three parameters; the registry fills eighteen; the candidate then
    looks complete because every field has a value, and a reader
    comparing success rates is comparing against a configuration nobody
    published.
    """
    stored = candidates.get(candidate_id)
    profile: dict[str, Any] = {}
    if payload.task_profile_id:
        try:
            profile = profiles.load(payload.task_profile_id).model_dump(mode="json")
        except Exception:
            profile = {}
    # Read from the stored spec, not from attributes `StoredCandidate`
    # does not have. `getattr(stored, "params", None)` returned None on
    # every call — the field is `spec`, and `stack` is `stack_label` —
    # so the diff was computed against the registry's defaults instead of
    # against this candidate. A candidate registered on `dwa_coarse`
    # reported `horizon_seconds = 1.5` where it actually runs 1.0, and
    # said the value had been defaulted when it had been chosen. Every
    # number a reader saw was wrong, which is the misattribution this
    # whole endpoint exists to prevent.
    spec = dict(stored.spec or {})
    comparison = build_comparison(
        payload.extraction,
        {
            "candidate_id": candidate_id,
            "stack": stored.stack_label or payload.extraction.get("stack", ""),
            "params": spec.get("params") or {},
        },
        profile,
    )
    items = [AdviceResource(**a.model_dump()) for a in reproduction_advice(comparison)]
    return ReproductionResource(
        candidate_id=candidate_id,
        parameters=list(comparison["parameters"]),
        **_advice_counts(items, len(REPRODUCTION_CODES)),
    )


@router.get("/decisions/{run_id}/outcome", response_model=AdviceListResource)
def decision_outcome(
    run_id: str,
    service: Runs,
    profiles: Profiles,
    request: Request,
    user: CurrentUser,
    use_model: Annotated[bool, Query()] = False,
) -> AdviceListResource:
    """Why this run ended the way it did — numbers joined to natures.

    The card says who won; the gate table says who was eliminated where.
    This says *why*, in two registers a reader can check separately: the
    stored numbers (which metric separated the field, whether the margin
    clears the noise), and the algorithms' own natures (a sampling
    planner's latency tail is its textbook price; the same tail on a
    deterministic planner is a surprise worth chasing). Every trait is
    anchored — a registry flag or the algorithm's defining mechanics —
    so the analysis never rests on folklore.

    Two refusals are built in rather than left to taste: a candidate
    eliminated at a gate is never described as "beaten" (nobody was
    compared), and an interval containing zero never yields a winner.

    ``use_model`` layers the LLM over the rules for the narrative — same
    constitution as everywhere: rank and extend, never remove.
    """
    stored = service.get(run_id)
    report = stored.report if isinstance(stored.report, dict) else dict(stored.report or {})
    profile: dict[str, Any] = {}
    try:
        profile = profiles.load(report.get("identity", {}).get("task_profile_id", "")).model_dump(
            mode="json"
        )
    except (NotFoundError, DomainValidationError):
        logger.warning("outcome: task profile unavailable for run %s", run_id)
        profile = {}
    source = build_outcome(report, profile)
    found = outcome_advice(source)
    if not use_model:
        items = [AdviceResource(**a.model_dump()) for a in found]
        return AdviceListResource(**_advice_counts(items, len(OUTCOME_CODES)))
    agent = get_agent_service(request, user)
    advised = advise_with_model("diagnosis", source, found, agent.provider)
    items = [
        AdviceResource(
            code=a.code,
            kind=a.kind,
            severity=a.severity,
            claim=a.claim,
            ground=a.ground,
            field_path=a.field_path,
            do=a.do,
            do_not=a.do_not,
            subject=a.subject,
            source=a.source,
        )
        for a in advised.advice
    ]
    return AdviceListResource(
        **_advice_counts(items, len(OUTCOME_CODES)),
        summary=advised.summary,
        fabricated=advised.fabricated,
        refused=advised.refused,
    )


@router.get("/task-profiles/{profile_id}/recommendation", response_model=RecommendationResource)
def task_profile_recommendation(
    profile_id: str,
    service: Runs,
    profiles: Profiles,
    map_root: MapRoot,
    request: Request,
    user: CurrentUser,
    use_model: Annotated[bool, Query()] = False,
) -> RecommendationResource:
    """Which algorithm should this deployment use, and in which cases.

    Everything here is read from stored runs on **this** profile: the
    card's verdict is repeated, never recomputed, and the per-mission
    split reuses the same paired bootstrap one aggregation level down.
    Feasibility on this profile trumps history — a stack preflight blocks
    is excluded however it fared elsewhere — and when no comparable
    history exists the honest answer is tier 3: "run this comparison",
    with the feasible field named.

    Read-only, like every advisory route. Adopting the recommendation is
    still a human act with a second person's approval (HĐ-14); there is
    no verb here that could do it.

    ``use_model`` layers the LLM over the rules — rank and extend, never
    remove, fabricated citations dropped and counted.
    """
    profile = profiles.load(profile_id)
    stored_runs = service.list(task_profile_id=profile_id)
    source = recommendation_source(
        profile,
        [
            {
                "run_id": stored.id,
                "status": stored.status,
                "card": stored.card,
                "report": stored.report,
                "created_at": stored.created_at,
                "contracts_version": stored.contracts_version,
            }
            for stored in stored_runs
        ],
        map_base_dir=map_root,
    )
    found = recommend_from_history(source)

    cases = [
        RecommendationCaseResource(run_id=row["run_id"], **case)
        for row in source["runs"]
        if row.get("case_table") and row["case_table"].get("available")
        for case in row["case_table"]["cases"]
    ]
    runs_considered = [row["run_id"] for row in source["runs"]]

    if not use_model:
        items = [AdviceResource(**a.model_dump()) for a in found]
        return RecommendationResource(
            task_profile_id=profile_id,
            evidence_tier=source["evidence_tier"],
            runs_considered=runs_considered,
            cases=cases,
            **_advice_counts(items, len(RECOMMENDATION_CODES)),
        )

    agent = get_agent_service(request, user)
    advised = advise_with_model("recommendation", source, found, agent.provider)
    items = [
        AdviceResource(
            code=a.code,
            kind=a.kind,
            severity=a.severity,
            claim=a.claim,
            ground=a.ground,
            field_path=a.field_path,
            do=a.do,
            do_not=a.do_not,
            subject=a.subject,
            source=a.source,
        )
        for a in advised.advice
    ]
    return RecommendationResource(
        task_profile_id=profile_id,
        evidence_tier=source["evidence_tier"],
        runs_considered=runs_considered,
        cases=cases,
        **_advice_counts(items, len(RECOMMENDATION_CODES)),
        summary=advised.summary,
        fabricated=advised.fabricated,
        refused=advised.refused,
    )


@router.get("/decisions/{run_id}/report-advice", response_model=AdviceListResource)
def decision_report_advice(run_id: str, service: Runs, user: CurrentUser) -> AdviceListResource:
    """What a reader may claim about this run, and what they may not.

    `report.md` renders the tables; this is the guardrail beside them.
    Every claim boundary the card's own shape supports — a
    NEAR_EQUIVALENT that must not be reported as a win, an interval
    containing zero that must not be quoted as a difference, a host-only
    latency screen that must not be called a real-time guarantee — comes
    back as advice with the barred sentence named.
    """
    stored = service.get(run_id)
    report = stored.report if isinstance(stored.report, dict) else dict(stored.report or {})
    found = report_advice(build_reporting_source(report, card=report.get("decision_card")))
    items = [AdviceResource(**a.model_dump()) for a in found]
    return AdviceListResource(**_advice_counts(items, len(REPORT_ADVICE_CODES)))


@router.get(
    "/decisions/{run_id}/traces/{candidate_id}/{episode_context_id}/review",
    response_model=TraceReviewResource,
)
def trace_review(
    run_id: str,
    candidate_id: str,
    episode_context_id: str,
    service: Runs,
    user: CurrentUser,
) -> TraceReviewResource:
    """Why this episode ended the way it did, from its own trace.

    The gate table says a candidate failed; the trace says what the
    robot was doing when it happened — clearance collapsing after a
    replan, angular velocity flapping sign, nine seconds parked short of
    the goal. The summary of those numbers is published beside the
    advice so every citation is checkable without re-opening the file.
    """
    summary = service.trace_summary(run_id, candidate_id, episode_context_id)
    found = trace_advice(summary)
    items = [AdviceResource(**a.model_dump()) for a in found]
    return TraceReviewResource(
        candidate_id=candidate_id,
        episode_context_id=episode_context_id,
        summary=summary,
        **_advice_counts(items, len(TRACE_REVIEW_CODES)),
    )


def _plugin_resource(draft: Any) -> PluginDraftResource:
    return PluginDraftResource(
        manifest=dict(draft.manifest),
        files=dict(draft.files),
        errors=list(draft.errors),
        notes=list(draft.notes),
        summary=draft.summary,
        refused=draft.refused,
        accepted=draft.accepted,
        provider=draft.provider,
        model=draft.model,
        deterministic=draft.deterministic,
    )


@router.post("/plugins/from-paper", response_model=PluginDraftResource)
def plugin_from_paper(
    payload: PluginRequest, request: Request, user: CurrentUser
) -> PluginDraftResource:
    """Draft an Algorithm Host plugin from a paper the platform cannot map.

    The candidate extractor refuses a method no existing stack
    implements — correctly. This is the way forward from that refusal:
    the host accepts algorithms as plugin bundles (manifest + code +
    entry point), so the model's output is forced into exactly that
    shape and then validated against the documented manifest rules.
    **Out of shape means rejected with the errors named**, never
    repaired. Nothing is stored, imported or executed — the bundle is a
    reviewed starting point, not a running algorithm.
    """
    agent = get_agent_service(request, user)
    return _plugin_resource(author_plugin(payload.text, agent.provider))


@router.post("/plugins/from-paper/upload", response_model=PluginDraftResource)
async def plugin_from_paper_upload(
    request: Request, user: CurrentUser, file: Annotated[UploadFile, File()]
) -> PluginDraftResource:
    """The same drafting, from a file instead of a paste."""
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise DomainValidationError(
            f"that file is {file.size // (1024 * 1024)} MB; the limit is "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
        )
    data = await file.read()
    try:
        text = read_upload(file.filename or "", data)
    except ValueError as exc:
        raise DomainValidationError(str(exc)) from exc
    agent = get_agent_service(request, user)
    return _plugin_resource(author_plugin(text[:MAX_PAPER_CHARS], agent.provider))


@router.post("/decisions/preflight", response_model=PreflightResource)
def preflight_decision(
    request: DecisionRequest,
    profiles: Profiles,
    map_root: MapRoot,
    user: CurrentUser,
) -> PreflightResource:
    """Say what is wrong with a comparison before it costs anything.

    **200, never 201 and never 4xx on a finding.** Nothing is created and
    nothing is refused: a pre-flight that could reject a launch would be a
    seventh gate written against a plan instead of against evidence, with
    none of a gate's guarantees. Every answer here is advice a person may
    read and overrule, and `POST /decisions` is untouched — a comparison
    this endpoint hates still runs if somebody asks for it.

    It takes the same body as the launch, so a caller pre-flights exactly
    what it is about to send rather than a paraphrase of it. That matters:
    the expensive mistakes are in the details — an episode count below
    what the declared collision risk needs, two entries that hash to one
    identity — and a summary would smooth over precisely those.

    The gates already catch most of this. They catch it after tens of
    minutes of simulation, because a gate reads evidence and evidence has
    to be produced first. This reads the request.
    """
    profile = profiles.load(request.task_profile_id)
    draft = build_draft(
        profile.model_dump(mode="json"),
        [spec.model_dump() for spec in request.candidates],
        scope=request.scope,
        episodes=request.episodes,
        map_base_dir=map_root,
    )
    found = preflight(draft)
    items = [AdviceResource(**advice.model_dump()) for advice in found]
    return PreflightResource(
        task_profile_id=request.task_profile_id,
        scope=request.scope,
        plan=PreflightPlan(**draft["plan"]),
        rules_applied=len(PREFLIGHT_CODES),
        advice=items,
        blocking=sum(1 for a in items if a.severity == "blocking"),
        material=sum(1 for a in items if a.severity == "material"),
        disclosure=sum(1 for a in items if a.severity == "disclosure"),
    )


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


@router.get("/decisions/{run_id}/critique", response_model=CritiqueResource)
def decision_critique(
    run_id: str,
    service: Runs,
    request: Request,
    user: CurrentUser,
    use_model: Annotated[bool, Query()] = False,
) -> CritiqueResource:
    """Objections to this run, for a reviewer to weigh before signing.

    Read-only and derived: nothing is stored, so a rule added tomorrow
    applies to every run already on disk. That is the point — the
    objections are a function of the report, not a property baked into it
    when it was written.

    An empty list is a result. It means the rules found nothing, not that
    the run is beyond question, and the response says how many rules ran
    so the two cannot be confused.

    ``use_model`` adds a language model on top of the rules: it orders
    them, writes a paragraph, and may add objections rules cannot reach —
    a straw-man baseline, a scope claimed wider than the run. It cannot
    remove a rule finding, and anything it cites that does not resolve in
    the report is dropped and counted in ``fabricated``. Off by default,
    because the deterministic answer is the one that reproduces.
    """
    stored = service.get(run_id)
    if not use_model:
        findings = critique(stored.report)
        return _critique_resource(
            run_id,
            [FindingResource(**f.model_dump(), source="rule") for f in findings],
        )

    agent = get_agent_service(request, user)
    result = critique_with_model(stored.report, agent.provider)
    return _critique_resource(
        run_id,
        [FindingResource(**f.model_dump()) for f in result.findings],
        summary=result.summary,
        fabricated=result.fabricated,
        refused=result.refused,
        provider=result.provider,
        model=result.model,
        deterministic=result.deterministic,
    )


def _critique_resource(
    run_id: str, findings: list[FindingResource], **extra: Any
) -> CritiqueResource:
    """Counts derived from the findings beside them, never passed in."""
    return CritiqueResource(
        run_id=run_id,
        rules_applied=len(RULE_CODES),
        findings=findings,
        blocking=sum(1 for f in findings if f.severity == "blocking"),
        material=sum(1 for f in findings if f.severity == "material"),
        disclosure=sum(1 for f in findings if f.severity == "disclosure"),
        omissions=sum(1 for f in findings if f.kind == "omission"),
        from_model=sum(1 for f in findings if f.source == "model"),
        **extra,
    )


@router.post("/candidates/from-paper", response_model=PaperExtractionResource)
def candidate_from_paper(
    payload: PaperRequest,
    request: Request,
    user: CurrentUser,
) -> PaperExtractionResource:
    """Recover a paper's reported configuration as a candidate draft.

    **Nothing is stored.** The response is a proposal: a person reads it,
    corrects what the model misread, and registers the candidate through
    ``POST /candidates`` if they agree. Skipping that step would make
    every number downstream rest on an extraction nobody checked.

    A paper whose method this platform does not implement comes back with
    no stack and a reason. That is the correct answer, not a failure —
    mapping it onto the nearest available planner would answer a
    different question with the paper's authority.
    """
    agent = get_agent_service(request, user)
    result = extract_from_paper(payload.text, agent.provider)
    return PaperExtractionResource(
        **result.model_dump(),
        offerable_stacks=list(selectable_stacks()),
        chars_read=len(payload.text),
        chars_total=len(payload.text),
    )


@router.post("/candidates/from-paper/upload", response_model=PaperExtractionResource)
async def candidate_from_paper_upload(
    request: Request,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> PaperExtractionResource:
    """The same extraction, from a file instead of a paste.

    **Still stores nothing** — not the file, not the text, not the draft.
    The upload exists to save a person the copy step, so keeping the PDF
    would add a thing to govern for no gain: whatever the reader
    registers goes through ``POST /candidates`` with a `candidate_id`
    that is a hash of the configuration, and the source PDF is not part
    of it.

    Reading is deliberately shallow — page text, joined. Whether a
    two-column layout interleaved is visible in the extracted quotes,
    which the reader is already checking. A layout-aware parser would be
    a second thing to be wrong about and would not make the model's
    reading of the numbers any better.
    """
    # Refused before the bytes are pulled into one `bytes` object.
    # Starlette reports the size once the part is spooled, and reading
    # first meant a gigabyte was received, written to a temp file and
    # made resident before the limit did anything but shape the message.
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise DomainValidationError(
            f"that file is {file.size // (1024 * 1024)} MB; the limit is "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
        )
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:  # a client that lied about its size
        raise DomainValidationError(
            f"that file is {len(data) // (1024 * 1024)} MB; the limit is "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
        )
    # PdfUnavailable is deliberately not caught: it has its own handler
    # and its own status, and flattening it into a 400 here would tell
    # the caller their file was wrong when the deployment was.
    try:
        text = read_upload(file.filename or "", data)
    except ValueError as exc:
        raise DomainValidationError(str(exc)) from exc

    agent = get_agent_service(request, user)
    result = extract_from_paper(text[:MAX_PAPER_CHARS], agent.provider)
    return PaperExtractionResource(
        **result.model_dump(),
        offerable_stacks=list(selectable_stacks()),
        # A 90k-character paper used to come back looking complete: a
        # stack, quoted parameters, and an `assumptions` list computed
        # over the first two thirds. Saying how much was read is the
        # difference between a partial reading and a wrong one.
        chars_read=min(len(text), MAX_PAPER_CHARS),
        chars_total=len(text),
    )


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


@router.get("/decisions/{run_id}/explanation")
def get_explanation(run_id: str, service: Runs) -> dict[str, Any]:
    """The case packet: the evidence behind this run's decision (E4.1).

    Built while the run was scored, not on the way out. The waterfall
    needs the scoring pass's own evidence objects, and reconstructing
    them here would mean a second implementation computing the same ΔU —
    so this route reads a block off the report and validates it.

    A run scored before E4.1 answers 409. It has no packet, and it
    cannot be given one without exactly the second implementation this
    design refused.
    """
    return service.explanation(run_id)


@router.get("/decisions/{run_id}/exemplars")
def get_exemplars(run_id: str, service: Runs) -> dict[str, Any]:
    """Which four episodes to look at, decided by a fixed recipe.

    Thirty episodes and one viewer: something has to choose which pair
    loads first, and a person choosing it is a choice that looks like
    evidence. The recipe returns the median episode, *both* extremes —
    they travel as a pair, since showing the winner's best without the
    runner-up's is the cherry-pick this exists to prevent — and the
    worst safety outcome, which the utility ranking never surfaces on
    its own.
    """
    return service.exemplars(run_id)


@router.get("/decisions/{run_id}/replay-sync/{episode_context_id}")
def get_replay_sync(
    run_id: str,
    episode_context_id: str,
    candidate_a: str,
    candidate_b: str,
    service: Runs,
    # Bounded, because this one parameter sizes both a loop and the
    # response body and the route needs no login to reach. `steps=1e9`
    # is not a client that wants a finer chart; the ceiling is far above
    # any real one — the page asks for 200.
    steps: Annotated[int, Query(ge=2, le=2000)] = 200,
) -> dict[str, Any]:
    """Both candidates of one episode, placed on arc length instead of the clock.

    The comparison page drives its two canvases from one playhead, which
    is time-sync and is the honest default: at a shared timestamp the
    two robots saw the same world. This endpoint serves the other view —
    the same part of the *map* for both — which is what makes a
    geometric cause visible and what silently changes the meaning of
    "at the same moment".

    So the payload carries its own caveat: the projection quality (the
    platform has no planned route to project onto yet, so today it is
    always a degraded one) and the fixed warning that the two runs
    reached each place at different times. A client cannot obtain the
    rows without them.

    Not a response model, for the reason :func:`get_trace` is not one:
    the rows are bulk telemetry, and the shape is already validated by
    the model that produced them.
    """
    return service.replay_sync(
        run_id,
        episode_context_id,
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        steps=steps,
    )


@router.post("/decisions/{run_id}/config-approval/withdraw", response_model=DecisionRunResource)
def withdraw_config(
    run_id: str, request: ReviewRequest, service: Runs, user: CurrentUser
) -> DecisionRunResource:
    """Take an approval back, leaving both acts in the journal.

    **Not an erasure.** The approve event stays and a withdraw event
    lands beside it, naming who took it back and why — which is what
    keeps HĐ-14 whole: an approval nobody could rely on would be no
    approval, and one that could vanish silently is exactly that.

    It exists because two doors were shut. Deleting a deployment refuses
    while any of its runs is approved, and a message telling somebody to
    withdraw an approval they cannot withdraw is a wall with a sign on
    it. And a configuration signed off in error had no way out but a new
    run measuring nothing new.

    The state returns to `pending`, not to `rejected`: withdrawing says
    "undecided again", not "decided against", and writing the second
    would record a verdict nobody reached.
    """
    return _run(
        service.withdraw_config(
            run_id,
            actor_user_id=user.id,
            username=user.nickname,
            comment=request.comment,
        )
    )


@router.get("/decisions/{run_id}/report.md", response_class=PlainTextResponse)
def decision_report_markdown(
    run_id: str, service: Runs, locale: ExportLocale = DEFAULT_EXPORT_LOCALE
) -> Response:
    """The whole run as one Markdown document, card or no card.

    **Exported for every run, not only ranked ones.** Fewer than two
    candidates through the gates means no ΔU and no card, and the gate
    table is then the deliverable — refusing to export it would make the
    ordinary outcome the one nobody can hand to a reviewer.

    Unlike `approved_config.yaml` this is not gated on approval: it is a
    description of what was measured, and reading it is the act that
    approval follows.

    ``locale`` defaults to English and a value outside the two languages
    is a 422 rather than a quiet fall back: a caller asking for a
    language nobody built should hear about it, not receive a document
    in a different one and assume it is the only one available.
    """
    from planbench_api.decision_markdown import (
        decision_report_filename,
        render_decision_markdown,
    )

    stored = service.get(run_id)
    return Response(
        content=render_decision_markdown(stored, locale),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{decision_report_filename(run_id)}"'
        },
    )


@router.get("/decisions/{run_id}/report.xlsx")
def decision_report_xlsx(
    run_id: str, service: Runs, locale: ExportLocale = DEFAULT_EXPORT_LOCALE
) -> Response:
    """The same run as a workbook, for a reader who works in a spreadsheet.

    Same content as ``report.md`` — `decision_export` decides every
    value and both renderers read it from there, so the two files cannot
    quote different numbers for one run.

    Exported for every run for the same reason the Markdown is: a run
    that ranked nobody still has a gate table, and that is the whole
    deliverable when fewer than two candidates cleared (HĐ-7).
    """
    from planbench_api.decision_xlsx import (
        decision_workbook_filename,
        render_decision_xlsx,
    )

    stored = service.get(run_id)
    return Response(
        content=render_decision_xlsx(stored, locale),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (f'attachment; filename="{decision_workbook_filename(stored)}"')
        },
    )


@router.get("/decisions/{run_id}/approved_config.yaml", response_class=PlainTextResponse)
def approved_config(run_id: str, service: Runs) -> str:
    """The deployable configuration — approved runs only (HĐ-14).

    Served as text rather than JSON because it is a file somebody saves,
    and because the sim-only notice inside it should be the first thing
    read rather than a field in a viewer.
    """
    return service.approved_config(run_id)
