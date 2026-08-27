"""Scenario library and leaderboard endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from planbench_api.auth import ActiveUser, ReadingUser
from planbench_api.dependencies import get_map_service, get_repos, get_scenario_service
from planbench_api.generalization import build_generalization_summary
from planbench_api.leaderboard import Leaderboard, ScoreWeights, build_leaderboard
from planbench_api.schemas import DynamicObstacleSnapshot
from planbench_api.services import MapService, ScenarioService
from planbench_benchmark import (
    CURRICULUM_ORDER,
    DifficultyCoverage,
    DifficultyLabel,
    GeneralizationSummary,
    ScenarioProtocolMetadata,
    ScenarioSplit,
    build_scenario,
    difficulty_coverage,
    get_difficulty,
    load_calibration,
    protocol_version,
    scenario_protocol_metadata,
)
from planbench_benchmark.difficulty import BaselineSpec
from planbench_schemas.dynamic import position_at
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario

router = APIRouter(tags=["library"])

Maps = Annotated[MapService, Depends(get_map_service)]
Scenarios = Annotated[ScenarioService, Depends(get_scenario_service)]


class LibraryEntry(BaseModel):
    name: str
    description: str
    curriculum_index: int
    dynamic_obstacles: int
    map_size_m: tuple[float, float]
    timeout_seconds: float
    #: Evaluation-protocol status (P05). Carried alongside the scenario,
    #: never inside it: the split is how the scenario is used, and the
    #: scenario's own definition — and therefore every conditions
    #: checksum ever computed from it — must not move when the protocol
    #: does.
    split: ScenarioSplit = "unassigned"
    protocol_version: str | None = None
    #: Why this scenario is held out (or is not). The reason is the only
    #: thing standing between a held-out set and "the ones we kept
    #: failing".
    split_notes: str | None = None
    #: Measured difficulty (P03), or None when nobody has calibrated this
    #: scenario. Null is the honest answer: ``curriculum_index`` is a
    #: hand-written intention about ordering, and quietly serving it as a
    #: difficulty would hide exactly the disagreement calibration exists
    #: to expose.
    difficulty: DifficultyLabel | None = None


class ImportedScenario(BaseModel):
    """IDs of the map and scenario created from a library entry."""

    library_name: str
    map_id: str
    scenario_id: str
    scenario: Scenario


class LibraryPreview(BaseModel):
    """A library entry drawn, without anything being stored.

    **Read-only on purpose.** The obvious way to preview an entry is to
    import it and look at the rows that come back, and that is how one
    database reached 198 maps carrying 41 distinct checksums: opening a
    form called the import endpoint, and every call stored a fresh map
    and scenario. Looking at something must not write it down.

    Carries the traffic already sampled, in the shape
    `/scenarios/preview` returns, so the browser plays it back with the
    code it already has and evaluates no motion law of its own.
    """

    library_name: str
    map: MapData
    scenario: Scenario
    dynamic_obstacles: tuple[DynamicObstacleSnapshot, ...] = ()
    duration: float = 0.0
    step: float = 0.0


@router.get("/scenario-library", response_model=list[LibraryEntry])
def list_library(_: ReadingUser) -> list[LibraryEntry]:
    """Built-in scenarios, ordered easiest to hardest (curriculum order)."""
    entries = []
    for index, name in enumerate(CURRICULUM_ORDER):
        map_data, scenario = build_scenario(name)
        protocol = scenario_protocol_metadata(name)
        entries.append(
            LibraryEntry(
                name=name,
                description=scenario.description,
                curriculum_index=index,
                dynamic_obstacles=len(scenario.dynamic_obstacles),
                map_size_m=(
                    map_data.width * map_data.resolution,
                    map_data.height * map_data.resolution,
                ),
                timeout_seconds=scenario.timeout_seconds,
                split=protocol.split,
                protocol_version=protocol.protocol_version,
                split_notes=protocol.notes,
                difficulty=get_difficulty(name),
            )
        )
    return entries


class DifficultyCalibrationSummary(BaseModel):
    """The measured difficulty scale, plus how well it covers the range.

    Read-only, like the protocol endpoint and for the same reason: these
    numbers are produced by ``scripts/calibrate_difficulty.py`` and are
    reproducible from it. A difficulty that can be set from a form is not
    a measurement.
    """

    calibration_version: str | None = None
    baseline: BaselineSpec | None = None
    #: One label per built-in scenario, in curriculum order. Entries the
    #: cache does not cover are simply absent — see ``coverage.uncalibrated``.
    scenarios: list[DifficultyLabel] = []
    coverage: DifficultyCoverage
    notes: str | None = None


@router.get("/difficulty-calibration", response_model=DifficultyCalibrationSummary)
def difficulty_calibration(_: ReadingUser) -> DifficultyCalibrationSummary:
    """Measured scenario difficulty against the pinned baseline (P03).

    Returns an empty scale rather than an error when nothing has been
    calibrated: "not measured" is a normal state of the platform, and the
    coverage warnings say so in words.
    """
    calibration = load_calibration()
    labels = [
        label for label in (get_difficulty(name) for name in CURRICULUM_ORDER) if label is not None
    ]
    return DifficultyCalibrationSummary(
        calibration_version=calibration.calibration_version if calibration else None,
        baseline=calibration.baseline if calibration else None,
        scenarios=labels,
        coverage=difficulty_coverage(),
        notes=calibration.notes if calibration else None,
    )


@router.get("/scenario-protocol", response_model=list[ScenarioProtocolMetadata])
def list_scenario_protocol(
    _: ReadingUser, scenario_name: str | None = Query(default=None)
) -> list[ScenarioProtocolMetadata]:
    """Dev/held-out classification of scenarios (P05).

    Read-only on purpose. Moving a scenario between splits is a change to
    the evaluation protocol — it is reviewed, versioned in
    ``scenario_protocol.json`` and shipped, not toggled from a form by
    whoever is unhappy with a result. Scenarios the file does not mention
    (anything created in the app) come back ``unassigned``.
    """
    if scenario_name is not None:
        return [scenario_protocol_metadata(scenario_name)]
    return [scenario_protocol_metadata(name) for name in CURRICULUM_ORDER]


@router.get("/scenario-library/{name}/preview", response_model=LibraryPreview)
def preview_library_scenario(
    name: str,
    _: ReadingUser,
    seed: int = Query(default=0, ge=0),
    step: float = Query(default=0.2, gt=0, le=5.0),
) -> LibraryPreview:
    """Show what a library entry actually does, storing nothing.

    The answer to "does this scenario behave the way its one-line
    description says" used to be: import it, build a deployment on it,
    open the test bench. Three steps and two stored rows to look at a
    picture.

    The traffic is sampled here rather than in the browser for the reason
    every other preview is: a second implementation of the motion laws
    would drift from the simulator's, and a preview that disagrees with
    the episode is worse than no preview.

    The span is the scenario's own `timeout_seconds`, so what plays is
    the length of episode this scenario declares rather than a number
    chosen here.
    """
    from planbench_api.errors import DomainValidationError

    try:
        map_data, scenario = build_scenario(name)
    except ValueError as exc:
        raise DomainValidationError(str(exc)) from exc

    duration = float(scenario.timeout_seconds)
    count = int(duration / step) + 1
    snapshots = tuple(
        DynamicObstacleSnapshot(
            name=obstacle.name,
            radius=obstacle.radius,
            position=position_at(obstacle, 0.0, seed),
            track=tuple(position_at(obstacle, index * step, seed) for index in range(count)),
        )
        for obstacle in scenario.dynamic_obstacles
    )
    return LibraryPreview(
        library_name=name,
        map=map_data,
        scenario=scenario,
        dynamic_obstacles=snapshots,
        duration=(count - 1) * step,
        step=step,
    )


@router.post(
    "/scenario-library/{name}/import",
    response_model=ImportedScenario,
    status_code=status.HTTP_201_CREATED,
)
def import_library_scenario(
    name: str, maps: Maps, scenarios: Scenarios, _: ActiveUser
) -> ImportedScenario:
    """Materialise a library scenario as a stored map + scenario pair."""
    from planbench_api.errors import DomainValidationError

    try:
        map_data, scenario = build_scenario(name)
    except ValueError as exc:
        raise DomainValidationError(str(exc)) from exc
    # **Adopt, do not create.** This endpoint is reached by the
    # deployment form simply *opening* — it needs a map to draw before
    # anybody has typed anything — and every call used to store a fresh
    # map and scenario. The row counts were a usage histogram of a
    # dropdown: 117 `static-obstacles`, the default the form opens on,
    # then 29 `sudden-stop`, 7 `crossing`, and so on down the list.
    #
    # A read-shaped action was writing, and the fix belongs here rather
    # than in the form: this endpoint has other callers, and the next one
    # would have made the same mess.
    stored_map = maps.adopt(map_data)
    stored_scenario = scenarios.adopt(stored_map.id, scenario)
    return ImportedScenario(
        library_name=name,
        map_id=stored_map.id,
        scenario_id=stored_scenario.id,
        scenario=scenario,
    )


@router.get("/leaderboard", response_model=Leaderboard)
def leaderboard(
    request_user: ActiveUser,
    repos=Depends(get_repos),  # noqa: B008 - FastAPI dependency
    scenario_name: str | None = Query(default=None),
    algorithm: str | None = Query(default=None),
    accepted_only: bool = Query(
        default=True,
        description=(
            "Only rank accepted benchmarks. Set false to inspect "
            "unreviewed runs — those must not be published as conclusions."
        ),
    ),
    group_by_observation_class: bool = Query(
        default=True,
        description=(
            "Keep stacks with different observation classes in separate "
            "groups. Set false to rank them together — the affected groups "
            "come back flagged, because the comparison is not like for like."
        ),
    ),
    weight_success: float = Query(default=0.40, ge=0),
    weight_safety: float = Query(default=0.30, ge=0),
    weight_efficiency: float = Query(default=0.20, ge=0),
    weight_smoothness: float = Query(default=0.10, ge=0),
) -> Leaderboard:
    """Rank stacks, grouped so only comparable results sit together."""
    weights = ScoreWeights(
        success=weight_success,
        safety=weight_safety,
        efficiency=weight_efficiency,
        smoothness=weight_smoothness,
    )
    return build_leaderboard(
        repos.benchmarks.list(),
        weights,
        scenario_name=scenario_name,
        algorithm=algorithm,
        accepted_only=accepted_only,
        group_by_observation_class=group_by_observation_class,
    )


@router.get("/generalization", response_model=GeneralizationSummary)
def generalization(
    request_user: ActiveUser,
    repos=Depends(get_repos),  # noqa: B008 - FastAPI dependency
    algorithm: str | None = Query(default=None),
    accepted_only: bool = Query(
        default=True,
        description=(
            "Only count accepted benchmarks. Set false to inspect unreviewed "
            "runs — a generalization claim from those is unreviewed too."
        ),
    ),
) -> GeneralizationSummary:
    """Dev-versus-held-out results per stack, plus the held-out audit trail.

    Each report contributes under the split it recorded when it ran, so
    re-classifying a scenario today does not rewrite yesterday's numbers.
    Reports whose scenario is unassigned are excluded and counted.
    """
    summary = build_generalization_summary(
        repos.benchmarks.list(), accepted_only=accepted_only, algorithm=algorithm
    )
    if not summary.protocol_versions:
        # No contributing report carried a version (all pre-P05 or all
        # unassigned). Say which protocol the reader is looking at now
        # rather than leaving the field blank.
        return summary.model_copy(update={"protocol_versions": (protocol_version(),)})
    return summary
