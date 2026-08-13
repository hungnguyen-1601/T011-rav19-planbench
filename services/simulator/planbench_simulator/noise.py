"""Seed-derived sensor and actuation noise (CONTRACTS HĐ-2, HĐ-3.2).

The simulator was fully deterministic, and that was a fidelity bug with a
measurable consequence. The only seed-dependent quantity was the phase of
the moving obstacles, so a **deterministic** stack on a mission whose
traffic never crosses its route drove the *same episode for every seed*.
A hundred such episodes bound a collision probability exactly as well as
one does — which is how a Decision Card came to print "0 collisions in
100 runs, 95% upper bound 3.0%" off a sample of one.

A real robot never runs twice the same: wheels slip, floors are wet,
LiDAR returns are noisy. Adding that back is **correcting a simulator
that was more optimistic than reality**, not adding randomness to make a
sample look healthier. Expect the numbers to get *worse*.

Two sources, and they are not the same kind of thing
----------------------------------------------------

===============  ==============================  ==========================
                 LiDAR range noise               Wheel slip
===============  ==============================  ==========================
Nature           measurement error               actuation error
Touches          ``Observation`` only            the **real** motion
Collision on     the true pose                   the true pose after slip
Why correct      the robot measures badly;       the robot really slipped;
                 the world did not move          the world records what
                                                 happened
===============  ==============================  ==========================

So LiDAR noise must never reach the collision test: judging contact on a
noisy pose would simulate a different world rather than a robot that
measures poorly. Slip does change the world, and that is its meaning.

Indexed, not consumed
---------------------

Every draw is a pure function of ``(seed, stream, step)``. It is **not**
"the next value from a generator", and the difference is load-bearing.

Two candidates run different numbers of steps and replan at different
moments. If noise were consumed sequentially from one stream, the order
of consumption would depend on candidate behaviour, so the two candidates
would meet *different noise* in episodes sharing one
``episode_context_id`` — two worlds under one id, which is exactly the
third fairness invariant broken (see ``tests/test_simulator_fairness.py``).

Indexing also makes a repeated query at the same step return the same
answer, which matters because ``get_observation`` may be called more than
once per step.

The trajectories of two candidates still differ, of course: they issue
different commands. That is the world reacting to the robot, not the
world favouring one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from planbench_schemas.sensor import SensorNoise

#: Stream tags mixed into the seed so the two sources can never draw the
#: same numbers. The values are arbitrary but **frozen**: changing one
#: changes every episode ever recorded under this model, which makes it a
#: contract change rather than a tidy-up.
_LIDAR_STREAM = 1
_SLIP_STREAM = 2
_DRIFT_STREAM = 3
_JUMP_STREAM = 4
_DROPOUT_STREAM = 5
_BIAS_STREAM = 6

#: Control steps a localisation estimate keeps a jump before the next
#: relocalisation window. A jump that lasted one step would be a spike a
#: controller never notices; the danger of a bad fix is that it *stays*.
_JUMP_WINDOW_STEPS = 40

#: How many sine components make up the drift. Three is enough to stop
#: the error looking periodic over an episode and few enough to stay
#: O(1) per query — which is what keeps every draw a pure function of
#: (seed, stream, step) rather than of how far this candidate happened
#: to drive.
_DRIFT_COMPONENTS = 3


@dataclass(frozen=True)
class NoiseModel:
    """Draws for one episode, fixed by that episode's seed.

    Constructed from the scenario, so a deployment that declares no noise
    (the default) produces a model whose every draw is exactly zero — old
    profiles keep their behaviour to the last float.
    """

    spec: SensorNoise
    seed: int

    @property
    def active(self) -> bool:
        return self.spec.active

    def lidar_offsets(self, step: int, count: int) -> np.ndarray | None:
        """Per-ray range error at ``step``, or ``None`` when disabled.

        Gaussian and zero-mean: a range finder that reads long as often
        as short. Applied to the measurement, never to the geometry.
        """
        sigma = self.spec.lidar_range_sigma_m
        if sigma <= 0.0 or count <= 0:
            return None
        return self._rng(_LIDAR_STREAM, step).normal(0.0, sigma, count)

    def slip_factors(self, step: int) -> tuple[float, float]:
        """Multipliers on the commanded velocities at ``step``.

        ``(1.0, 1.0)`` when disabled. A fraction of 0.02 means the wheels
        deliver 2% more or less than asked, one standard deviation — the
        amplitude the topic document's noise-axis table names.

        The factors for linear and angular motion are drawn separately:
        a differential drive slips per wheel, so a slip that always moved
        both the same way could never produce the veer that actually
        happens.
        """
        fraction = self.spec.wheel_slip_fraction
        if fraction <= 0.0:
            return (1.0, 1.0)
        draws = self._rng(_SLIP_STREAM, step).normal(0.0, fraction, 2)
        return (1.0 + float(draws[0]), 1.0 + float(draws[1]))

    def dropout_mask(self, step: int, count: int) -> np.ndarray | None:
        """Which rays return nothing at ``step``, or ``None`` when disabled.

        Bernoulli, not Gaussian — a return either comes back or it does
        not. Glass, mirrors and dark surfaces are the physical cause, and
        the consequence is the one that matters: a dropped return reads
        to a costmap as **free space**, which is how a real robot drives
        into a glass door.

        The caller reports a dropped ray as **maximum range**, never as
        zero. Zero is "an obstacle touching the sensor", the opposite
        reading, and it would make dropout the safest thing that can
        happen to a planner instead of the most dangerous.
        """
        probability = self.spec.lidar_dropout_probability
        if probability <= 0.0 or count <= 0:
            return None
        return self._rng(_DROPOUT_STREAM, step).random(count) < probability

    def pose_error(self, step: int) -> tuple[float, float, float]:
        """How wrong the robot's idea of its own pose is at ``step``.

        ``(dx, dy, dtheta)``, all zero when disabled. **Measurement
        only** — it reaches ``Observation.pose`` and never the collision
        test, exactly like LiDAR range error. A collision judged on a
        believed pose would simulate a different world rather than a
        robot that does not know where it is.

        Two components, because they fail differently:

        **Drift** is slow and correlated: a sum of a few low-frequency
        sinusoids whose amplitudes and phases come from the seed. A
        zero-mean per-step jitter would be the wrong model and a
        comfortable one — a controller averages jitter away and cannot
        average away an estimate that is wrong in the same direction for
        twenty seconds.

        **Jumps** are a step change that *stays*, held for a
        relocalisation window. A controller can ride out a slow error and
        cannot ride out a discontinuity, so modelling only drift would
        miss the failure that actually strands robots.

        Indexed like everything else here: the value at a step is a pure
        function of ``(seed, step)`` and not of how far this candidate
        drove to get there. Accumulating along the travelled path would
        be more physical and would make the noise depend on candidate
        behaviour, which is the one thing this module exists to prevent.
        """
        drift = self.spec.localization_drift_m
        jump_probability = self.spec.localization_jump_probability
        if drift <= 0.0 and jump_probability <= 0.0:
            return (0.0, 0.0, 0.0)

        dx = dy = dtheta = 0.0
        if drift > 0.0:
            shape = self._rng(_DRIFT_STREAM, 0)
            phases = shape.uniform(0.0, 2.0 * np.pi, (3, _DRIFT_COMPONENTS))
            # Periods spread over tens to hundreds of steps: fast enough
            # to move within an episode, slow enough that the estimate is
            # wrong in one direction for a while.
            periods = shape.uniform(60.0, 400.0, (3, _DRIFT_COMPONENTS))
            weights = shape.dirichlet(np.ones(_DRIFT_COMPONENTS), size=3)
            waves = np.sin(2.0 * np.pi * step / periods + phases)
            dx, dy, dtheta = (weights * waves).sum(axis=1) * drift
            # Heading error scales with the position error rather than
            # carrying its own amplitude: they come from one bad fix.
            dtheta = float(dtheta) * 0.5

        if jump_probability > 0.0:
            window = step // _JUMP_WINDOW_STEPS
            draw = self._rng(_JUMP_STREAM, window)
            if float(draw.random()) < jump_probability:
                # Sized against the drift so one profile field governs
                # "how wrong can this estimate be", with the jump landing
                # at the upper end of it.
                magnitude = max(drift, 0.25)
                angle = float(draw.uniform(0.0, 2.0 * np.pi))
                dx += magnitude * float(np.cos(angle))
                dy += magnitude * float(np.sin(angle))

        return (float(dx), float(dy), float(dtheta))

    def odometry_bias(self) -> tuple[float, float]:
        """Per-episode systematic error in delivered velocity.

        ``(1.0, 1.0)`` when disabled. Drawn **once for the episode** and
        held, which is the whole difference from wheel slip: slip is
        zero-mean per step so its error averages out, while a wheel worn
        smaller than its partner is wrong in one direction every step and
        the error **accumulates**. Two failure modes, and until now only
        the forgiving one was simulated.

        Changes the real motion, like slip — the robot really did travel
        further than it was told to.
        """
        fraction = self.spec.odometry_bias_fraction
        if fraction <= 0.0:
            return (1.0, 1.0)
        draws = self._rng(_BIAS_STREAM, 0).normal(0.0, fraction, 2)
        return (1.0 + float(draws[0]), 1.0 + float(draws[1]))

    def _rng(self, stream: int, step: int) -> np.random.Generator:
        """A generator for exactly one (stream, step) cell.

        Built fresh each call rather than kept as state. That is the
        whole point — see the module docstring — and it costs a few
        microseconds against an episode step that costs milliseconds.

        ``SeedSequence`` over the triple rather than ``seed + step``:
        adjacent seeds must not produce correlated streams, and its
        hashing is what guarantees that.
        """
        return np.random.Generator(
            np.random.PCG64(np.random.SeedSequence([self.seed, stream, step]))
        )
