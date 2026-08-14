"""Prediction with perfect perception — a measuring instrument, not a candidate.

**The question this answers.** ``dwa_predictive`` will estimate obstacle
velocities from LiDAR, and estimation error is part of the algorithm. So
if the comparison against ``dwa`` comes out flat, there are two
explanations and no way to tell them apart: *the constant-velocity model
is not worth anything here*, or *the model is fine and the tracker is
bad*. This module removes the second by handing the controller the
velocities the simulator itself is using. Whatever prediction is worth,
it is worth **at most** this.

That makes it decision gate 2 of the plan, and the cheapest place to
cancel the whole thing: if perfect perception buys nothing measurable on
scenes inside the model's own assumption, no tracker can rescue it.

**It is never a candidate, and that is guaranteed by structure rather
than by a flag.** It cannot be registered even if somebody wanted to: the
registry's factory is ``config -> LocalPlanner`` and has no scenario to
close a ground-truth provider over. So there is no path from here to
``/candidates``, to a Decision Card, or to the UI, and nobody has to
remember not to build one. The distinct ``name`` is the second line of
defence, so a record produced by this thing cannot be mistaken for one
produced by the benchmarkable candidate.

**What the oracle may know: the present. Not the future.**

    position:  position_at(obstacle, t, seed)
    velocity:  (position_at(t) - position_at(t - dt)) / dt      <- backward

The difference is one-sided and looks **into the past** on purpose.
``position_at(t + eps)`` would be reading the future, and an oracle that
reads the future stops measuring *perception* and starts measuring
*clairvoyance* — at which point the gap between it and the tracker mixes
estimation error with model error and neither is readable.

The same rule produces the behaviour that proves the constraint holds. On
``sudden_stop`` the oracle keeps extrapolating straight **through** the
moment the cart parks, because a backward difference cannot know about a
stop that has not happened yet. It recovers one ``dt`` later, when the
stop has become the past. A tracker recovers after its own estimation
window instead, and the difference between those two lags is part of what
P5 measures.
"""

from __future__ import annotations

from planbench_planning.dwa_predictive.planner import DWAPredictiveConfig, DWAPredictivePlanner
from planbench_planning.dwa_predictive.tracks import ObstacleTrack
from planbench_schemas.dynamic import position_at
from planbench_schemas.geometry import Point2D
from planbench_schemas.scenario import Scenario

__all__ = ["DWAOraclePredictive", "GroundTruthObstacleProvider"]


class GroundTruthObstacleProvider:
    """Obstacle tracks read from the motion laws, with no sensing error.

    **Closes over the scenario, not over the engine**, and that is what
    makes it possible at all. ``run_stack`` builds its own
    ``SimulationEngine`` internally, so a caller never holds the engine to
    close over — an earlier design assumed otherwise and could not have
    been implemented. It does not matter: the motion laws are pure
    functions, and the engine itself reads obstacles through
    ``position_at(obstacle, time, scenario.random_seed)``. Reconstructing
    from ``(scenario, seed)`` therefore reproduces what the engine sees
    bit for bit rather than approximating it.
    """

    def __init__(self, scenario: Scenario, difference_seconds: float) -> None:
        if difference_seconds <= 0.0:
            raise ValueError("the backward difference needs a positive interval")
        self._obstacles = scenario.dynamic_obstacles
        self._seed = scenario.random_seed
        self._dt = difference_seconds

    def __call__(self, time: float) -> tuple[ObstacleTrack, ...]:
        tracks = []
        for obstacle in self._obstacles:
            here = position_at(obstacle, time, self._seed)
            if time < self._dt:
                # **Warm-up, and it is deliberately the tracker's rule.**
                # There is no past to difference against yet, so the
                # honest answer is "not moving, as far as anything can
                # tell". Guessing from a single sample would be inventing
                # a velocity, and the tracker of P5 will refuse the same
                # way — the two must agree wherever neither has
                # information, or the gap between them stops being
                # estimation error.
                velocity = Point2D(x=0.0, y=0.0)
            else:
                before = position_at(obstacle, time - self._dt, self._seed)
                velocity = Point2D(
                    x=(here.x - before.x) / self._dt,
                    y=(here.y - before.y) / self._dt,
                )
            tracks.append(
                ObstacleTrack(
                    center=here,
                    radius=obstacle.radius,
                    velocity=velocity,
                    # Perfect perception is perfectly confident. A tracker
                    # lowers this; the oracle never does, which is exactly
                    # the difference being measured.
                    confidence=1.0,
                )
            )
        return tuple(tracks)


class DWAOraclePredictive(DWAPredictivePlanner):
    """``dwa_predictive`` with the estimation error taken out.

    Subclassing is right here and wrong for ``dwa_predictive`` versus
    ``dwa``, which is worth being explicit about because the module
    docstring of the planner forbids exactly this shape. The rule it
    states is about **two candidates** sharing an implementation: a fix in
    the parent would change both while both recorded ids stayed put. This
    class is not a candidate and has no id — it is the same candidate with
    a different information source, and a subclass says that precisely.

    The only override is the name, and it earns its place: it means a
    trace, a log line or a stray artifact produced by this instrument can
    never be read as evidence about the benchmarkable candidate.
    """

    @property
    def name(self) -> str:
        return "dwa_oracle_predictive"


def build_oracle(
    scenario: Scenario,
    config: DWAPredictiveConfig | None = None,
) -> DWAOraclePredictive:
    """The oracle wired to one scenario's ground truth.

    The backward-difference interval is the scenario's own
    ``simulation_dt``: the oracle should difference over the same tick the
    world is stepped with, so its velocity is the one the simulator just
    used rather than an average over some other window.
    """
    config = config or DWAPredictiveConfig()
    return DWAOraclePredictive(
        config,
        provider=GroundTruthObstacleProvider(scenario, scenario.simulation_dt),
    )
