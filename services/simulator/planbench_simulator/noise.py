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
