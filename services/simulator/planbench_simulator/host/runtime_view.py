"""The narrow seam between the engine and the provider graph (H3).

**Providers never receive the engine.** They receive this: a frozen set
of closures over exactly what a provider may legitimately read — the
clock, the tick counter, the robot state, the measurement the robot
actually took, the planning grid. Principle 3 of the plan says a plugin
must not be handed ``Engine``, ``Scenario`` or a world-truth callback,
and the way to mean it is to have nothing to hand over.

**Ground truth is gated, not absent.** ``GroundTruthTrackProvider``
exists and must read the real obstacle positions — that is what makes it
an *oracle* provider, and measuring an upper bound is a first-class use
(P4 did exactly this). So the truth closure lives here behind
:meth:`private_truth`, which refuses any requester outside
:data:`TRUSTED_ORACLE_PROVIDERS`. A provider cannot reach world truth by
renaming itself, because the allowlist is keyed on the class object, not
on a string it supplies.

This is a **trust policy, not hard isolation**, and the plan says so
outright (§5.7): code in one process can reach into another object.
Hard isolation is what the subprocess lane buys (H7). What this buys is
that the honest path is the declared one, and a dishonest one has to be
written deliberately rather than reached for by accident.

**Randomness is addressable, never stateful** (§5.4, round-3 contract).
:meth:`rng` derives a generator from ``(episode seed, stream id, tick,
index)`` exactly the way :class:`~planbench_simulator.noise.NoiseModel`
does, so two providers reading the same tick get the same draw
regardless of the order the graph walks them in, and re-reading a tick
is free of consequence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from planbench_schemas.episode import Observation
from planbench_schemas.robot import RobotState
from planbench_schemas.scenario import CircleObstacle
from planbench_simulator.grid import OccupancyGrid


class OracleAccessDenied(PermissionError):
    """A provider outside the oracle allowlist reached for world truth."""


#: Provider classes allowed to read ground truth in the MVP. A tuple of
#: *class objects*: membership cannot be spoofed by a provider that
#: declares a convenient ``capability`` or ``name``. Adding an entry is
#: a fairness decision — every channel it produces is ``sim_only`` and
#: taints the whole execution's evidence class (§5.10).
TRUSTED_ORACLE_PROVIDERS: tuple[type, ...] = ()


def register_trusted_oracle(provider_class: type) -> None:
    """Admit one provider class to the ground-truth allowlist.

    Called by the built-in oracle module at import. Kept as a function so
    the allowlist is append-only from one direction and a test can assert
    exactly who is on it.
    """
    global TRUSTED_ORACLE_PROVIDERS
    if provider_class not in TRUSTED_ORACLE_PROVIDERS:
        TRUSTED_ORACLE_PROVIDERS = (*TRUSTED_ORACLE_PROVIDERS, provider_class)


@dataclass(frozen=True)
class ProviderRuntimeView:
    """Everything a provider may ask the simulation, and nothing else."""

    #: Simulation clock, seconds. The authority for ``per_tick``
    #: freshness: a channel claiming another time is refused.
    now: Callable[[], float]
    #: Monotonic control-tick counter.
    tick: Callable[[], int]
    #: True robot state — pose the *simulator* knows. Providers that
    #: model perception must use ``measured_observation`` instead; this
    #: exists for the state channel the loop already grants every stack.
    robot_state: Callable[[], RobotState]
    #: What the robot measured this tick: believed pose, noisy ranges.
    measured_observation: Callable[[], Observation]
    #: The static planning grid for this episode.
    planning_grid: Callable[[], OccupancyGrid]
    #: Seed of this episode, for addressable randomness.
    episode_seed: int = 0
    #: Ground truth, reachable only through :meth:`private_truth`.
    _truth: Callable[[], tuple[CircleObstacle, ...]] | None = field(default=None, repr=False)

    def private_truth(self, requester: Any) -> tuple[CircleObstacle, ...]:
        """Ground-truth obstacles, for an allowlisted oracle provider only.

        ``requester`` is the provider instance asking. The check is on
        its class, so the refusal cannot be talked out of.
        """
        if type(requester) not in TRUSTED_ORACLE_PROVIDERS:
            raise OracleAccessDenied(
                f"{type(requester).__name__} is not an allowlisted oracle provider and "
                "may not read world truth; a candidate that reads it is not measuring "
                "perception, and the ranking would credit it for information no robot has"
            )
        if self._truth is None:
            raise OracleAccessDenied(
                "this runtime view carries no truth closure; the host was wired "
                "without one, so no oracle channel can be produced here"
            )
        return self._truth()

    @classmethod
    def over_engine(
        cls,
        engine: Any,
        planning_grid: OccupancyGrid,
        *,
        episode_seed: int = 0,
        grant_truth: bool = False,
    ) -> ProviderRuntimeView:
        """Build the seam over a live engine — closures, not the engine.

        This is the whole point of the class rendered as code: the engine
        goes in, five bound methods come out, and the object handed
        onwards has no attribute through which the engine, the scenario
        or the episode's internals can be reached. ``grant_truth`` is the
        deployment's decision to run an oracle lane at all; without it
        the view carries no truth closure and even an allowlisted
        provider gets a refusal rather than data.
        """
        return cls(
            now=lambda: engine.time,
            tick=lambda: engine.steps,
            robot_state=engine.get_state,
            measured_observation=engine.get_observation,
            planning_grid=lambda: planning_grid,
            episode_seed=episode_seed,
            _truth=engine.dynamic_obstacles_now if grant_truth else None,
        )

    def rng(self, stream_id: int, tick: int, index: int = 0) -> np.random.Generator:
        """A generator addressed by ``(seed, stream, tick, index)``.

        Counter-based, so it depends on *what* is being drawn rather than
        on how many draws happened before — which is what makes a
        provider's output independent of the order the graph walked it in
        and safe to recompute.
        """
        return np.random.Generator(
            np.random.PCG64(np.random.SeedSequence([self.episode_seed, stream_id, tick, index]))
        )
