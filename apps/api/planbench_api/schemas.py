"""API request/response models (wrap the domain schemas, never replace them)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planbench_benchmark import ScenarioSplit
from planbench_metrics import EpisodeMetrics
from planbench_planning import PlanResult
from planbench_schemas.episode import EpisodeResult
from planbench_schemas.geometry import Point2D
from planbench_schemas.map import MapData
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.scenario import Scenario


class MapResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: int
    checksum: str
    created_at: str
    map_data: MapData


class MapSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: int
    name: str
    width: int
    height: int
    resolution: float
    checksum: str
    created_at: str


class ScenarioCreateRequest(BaseModel):
    map_id: str
    scenario: Scenario


class ScenarioResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: int
    map_id: str
    created_at: str
    scenario: Scenario
    #: Evaluation split (P05), resolved read-only from the protocol file.
    #: Anything authored in the app is ``unassigned``, and there is no
    #: request field that can change that: promoting a scenario is a
    #: reviewed protocol change, not something the author of a scenario
    #: decides about their own scenario.
    split: ScenarioSplit = "unassigned"


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    errors: tuple[str, ...] = ()


class DynamicObstacleSnapshot(BaseModel):
    """Where one moving obstacle is at a given instant, and where it goes.

    **`track` is the whole point of asking once.** A still frame at the
    instant somebody typed answers "is the cart in my way at t = 12" and
    not "where is it heading", which is the question an author placing a
    start pose actually has. Animating it by calling this endpoint per
    frame would be a round trip every 40 ms; sampling the same pure
    `position_at` server-side is one call and cannot drift from it.

    `position` stays, and stays first: it is the instant the request
    named, and a caller that only wants the still frame should not have
    to know the track exists.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    radius: float
    position: Point2D
    #: Positions from t=0 to the requested duration, one every `step`
    #: seconds. Empty when no duration was asked for.
    track: tuple[Point2D, ...] = ()


class ScenarioPreviewRequest(BaseModel):
    """Ask the backend where everything is at ``time``.

    The UI does not evaluate motion laws itself. Every position it draws
    comes from here, computed by the same ``position_at`` the simulator
    uses — otherwise the preview could disagree with the episode, and a
    scenario editor whose preview lies is worse than no preview.
    """

    map_id: str
    scenario: Scenario
    #: Seconds into the episode. 0 is the state the robot starts in.
    time: float = Field(default=0.0, ge=0)
    #: Episode seed. Timing of seeded traffic depends on it, so the
    #: preview states which seed it is showing rather than implying the
    #: scenario looks like this for all of them.
    seed: int = 0
    #: Seconds of motion to sample, from 0. `None` asks for the instant
    #: alone — the shape this endpoint had before playback existed, kept
    #: so a caller that wants one frame still gets one reply's worth of
    #: work.
    duration: float | None = Field(default=None, gt=0, le=600)
    #: Seconds between samples. The client plays the track back at its
    #: own rate, so this is resolution rather than frame rate: fine
    #: enough that a cart's turn is a curve, coarse enough that a
    #: ten-minute episode is not a hundred thousand points.
    step: float = Field(default=0.2, gt=0, le=5.0)


class ScenarioPreview(BaseModel):
    """Obstacle positions at one instant, plus the validation verdict.

    Validation travels with the preview because the editor always needs
    both: a scenario whose start pose sits inside a wall must say so
    while it is being drawn, not when it is saved.
    """

    model_config = ConfigDict(frozen=True)

    time: float
    seed: int
    valid: bool
    errors: tuple[str, ...] = ()
    dynamic_obstacles: tuple[DynamicObstacleSnapshot, ...] = ()
    #: What the tracks span, echoed back. The client labels its scrubber
    #: from these rather than from what it asked for: the two differ
    #: whenever the request was clamped, and a scrubber that reads 600 s
    #: over a 60 s track is the same lie as a canvas labelled t = 40
    #: showing t = 0.
    duration: float = 0.0
    step: float = 0.0


class SimulationCreateRequest(BaseModel):
    map_id: str
    scenario_id: str
    algorithm: str = "astar+dwa"
    config: dict = Field(default_factory=dict)
    #: Whether this robot may ask for a new global path when it gets
    #: blocked. Omitted means no, which is what every simulation created
    #: before this field existed did. ``ReplanningConfig`` itself rejects
    #: ``enabled`` with a budget of zero — a switch that turns nothing on
    #: is the worst of the three states, because the result then claims a
    #: capability it never used.
    replanning: ReplanningConfig = NO_REPLANNING


class SimulationResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    map_id: str
    scenario_id: str
    algorithm: str
    config: dict = Field(default_factory=dict)
    state: str  # created | finished
    created_at: str
    #: Echoed back so a client never has to remember what it asked for,
    #: and so a stored simulation can be read for what it actually ran.
    replanning: ReplanningConfig = NO_REPLANNING


class SimulationResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    state: str
    plan: PlanResult | None = None
    result: EpisodeResult | None = None
    metrics: EpisodeMetrics | None = None


class DeploymentState(BaseModel):
    """What kind of deployment this is, for the interface to say so.

    On the health endpoint rather than behind a session, because the
    banner it feeds has to be up before anybody signs in: "this machine
    approves its own work" is context for reading the login page too.
    Neither field is a secret — both describe rules, not data.
    """

    model_config = ConfigDict(frozen=True)

    profile: str
    separation_of_duties: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    app: str
    version: str
    deployment: DeploymentState | None = None
