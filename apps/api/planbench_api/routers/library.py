"""Scenario library and leaderboard endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from planbench_api.auth import ActiveUser
from planbench_api.dependencies import get_map_service, get_repos, get_scenario_service
from planbench_api.generalization import build_generalization_summary
from planbench_api.leaderboard import Leaderboard, ScoreWeights, build_leaderboard
from planbench_api.services import MapService, ScenarioService
from planbench_benchmark import (
    CURRICULUM_ORDER,
    GeneralizationSummary,
    ScenarioProtocolMetadata,
    ScenarioSplit,
    build_scenario,
    protocol_version,
    scenario_protocol_metadata,
)
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


class ImportedScenario(BaseModel):
    """IDs of the map and scenario created from a library entry."""

    library_name: str
    map_id: str
    scenario_id: str
    scenario: Scenario


@router.get("/scenario-library", response_model=list[LibraryEntry])
def list_library() -> list[LibraryEntry]:
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
            )
        )
    return entries


@router.get("/scenario-protocol", response_model=list[ScenarioProtocolMetadata])
def list_scenario_protocol(
    scenario_name: str | None = Query(default=None),
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
    stored_map = maps.create(map_data)
    stored_scenario = scenarios.create(stored_map.id, scenario)
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
