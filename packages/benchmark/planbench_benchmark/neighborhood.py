"""Task Neighborhood: does the recommendation survive the input being wrong? (N5)

**This answers a different question from the evaluation set, and the two
get confused constantly.**

============  =========================================  ==================
              Asks                                       Uncertainty about
============  =========================================  ==================
Evaluation    "How does this candidate do on the         the **workload**
              missions I will actually run?"
Neighborhood  "If the map and sensor model I handed      the **input**
              you are a little off, does your advice
              still hold?"
============  =========================================  ==================

A perfect mission distribution does not remove the need for the second:
a map is a measurement with error, and a pallet is not where the drawing
says it is. HĐ-11.5 calls the resulting number ``robustness_margin``, and
it has been ``null`` on every Decision Card this project has produced —
which HĐ-12 reads as *"not measured"*, honestly but emptily.

**A variant is identified by what it does, not by its position in a
list.** ``variant_id`` is a content hash of the perturbation, so
"variant 3" from two different generator versions cannot silently mean
two different worlds — the same class of bug ``episode_context_id``
exists to prevent, and one that would be invisible here because both
runs would look complete.

**Deterministic from the profile and the seed.** Two people asking for
the neighbourhood of one deployment must get the same neighbourhood, or
``robustness_margin`` is not a number anybody can check.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from planbench_schemas.identity import canonical_json, sha256_short
from planbench_schemas.task_profile import TaskProfile

__all__ = [
    "AXES",
    "Perturbation",
    "Variant",
    "neighborhood_variants",
    "recommendation_robustness",
]

#: Hex digits kept of a perturbation's hash, matching
#: ``EPISODE_CONTEXT_ID_LENGTH``: the variant id ends up inside a context
#: id, and two identifier lengths in one hash chain is a difference
#: nobody would be able to explain later.
_VARIANT_ID_LENGTH = 12

#: The amplitudes of the topic document's noise-axis table (N5).
#:
#: Written as data rather than as literals in the code so the table and
#: the generator cannot drift, and so a reader can compare them side by
#: side. Every entry is a *deployment* property being nudged, never a
#: candidate one — perturbing something a candidate declares would be
#: perturbing the thing under test.
AXES: dict[str, float] = {
    #: Pick-up and drop-off points are not fixed to the millimetre.
    "start_goal_shift_m": 1.0,
    "start_goal_heading_rad": math.radians(15.0),
    #: Different shifts: a busier hour, a slower cart.
    "traffic_speed_scale": 0.2,
    #: A robot carrying a load, or on a tired battery.
    "v_max_scale": 0.1,
    #: A wetter floor and a dirtier scanner than the day noise was
    #: characterised. Scales the declared amplitudes; it does not invent
    #: them for a deployment that declared none.
    "noise_scale": 0.5,
}


@dataclass(frozen=True)
class Perturbation:
    """One structured deviation from the nominal profile.

    Fractions and offsets rather than absolute values, so one
    perturbation means the same nudge applied to any deployment.
    """

    start_dx: float
    start_dy: float
    start_dtheta: float
    goal_dx: float
    goal_dy: float
    goal_dtheta: float
    traffic_speed: float
    v_max: float
    noise: float

    def as_payload(self) -> dict[str, float]:
        return {
            "start_dx": round(self.start_dx, 6),
            "start_dy": round(self.start_dy, 6),
            "start_dtheta": round(self.start_dtheta, 6),
            "goal_dx": round(self.goal_dx, 6),
            "goal_dy": round(self.goal_dy, 6),
            "goal_dtheta": round(self.goal_dtheta, 6),
            "traffic_speed": round(self.traffic_speed, 6),
            "v_max": round(self.v_max, 6),
            "noise": round(self.noise, 6),
        }


@dataclass(frozen=True)
class Variant:
    """A perturbed profile and the id that names the perturbation."""

    variant_id: str
    profile: TaskProfile
    perturbation: Perturbation


def _draw(rng: np.random.Generator, amplitude: float) -> float:
    """A nudge in ``[-amplitude, +amplitude]``.

    Uniform rather than Gaussian, and that is the right shape here: the
    axes describe a *range* somebody is willing to be wrong by — "the
    pallet is within a foot of the drawing" — not a distribution of
    measurement error around a true value. A Gaussian would put most
    variants near nominal and answer a softer question than the one
    asked.
    """
    return float(rng.uniform(-amplitude, amplitude))


def _perturbation(rng: np.random.Generator) -> Perturbation:
    return Perturbation(
        start_dx=_draw(rng, AXES["start_goal_shift_m"]),
        start_dy=_draw(rng, AXES["start_goal_shift_m"]),
        start_dtheta=_draw(rng, AXES["start_goal_heading_rad"]),
        goal_dx=_draw(rng, AXES["start_goal_shift_m"]),
        goal_dy=_draw(rng, AXES["start_goal_shift_m"]),
        goal_dtheta=_draw(rng, AXES["start_goal_heading_rad"]),
        traffic_speed=1.0 + _draw(rng, AXES["traffic_speed_scale"]),
        v_max=1.0 + _draw(rng, AXES["v_max_scale"]),
        noise=1.0 + _draw(rng, AXES["noise_scale"]),
    )


def _apply(profile: TaskProfile, perturbation: Perturbation) -> TaskProfile:
    """The nominal profile with one perturbation applied.

    **The id is left alone on purpose.** A variant is not a new
    deployment: it is the same deployment asked a what-if, and its
    episodes are told apart by ``environment_variant`` in the context
    hash (HĐ-3.1). Giving it a new ``task_profile_id`` would file a
    deployment nobody deployed, and its runs would then look like
    evidence about a real site.
    """
    payload = profile.model_dump(mode="python")

    missions = []
    for mission in payload["missions"]:
        start, goal = dict(mission["start"]), dict(mission["goal"])
        start["x"] += perturbation.start_dx
        start["y"] += perturbation.start_dy
        start["theta"] += perturbation.start_dtheta
        goal["x"] += perturbation.goal_dx
        goal["y"] += perturbation.goal_dy
        goal["theta"] += perturbation.goal_dtheta
        missions.append({**mission, "start": start, "goal": goal})
    payload["missions"] = missions

    payload["robot"] = {
        **payload["robot"],
        "max_linear_velocity": payload["robot"]["max_linear_velocity"] * perturbation.v_max,
    }

    environment = dict(payload["environment"])
    # Scaled, never introduced. A deployment that declared no noise is
    # one nobody characterised, and inventing an amplitude for it here
    # would answer a question about a world the author did not describe.
    noise = dict(environment["sensor_noise"])
    for key in ("lidar_range_sigma_m", "wheel_slip_fraction"):
        noise[key] = noise[key] * perturbation.noise
    environment["sensor_noise"] = noise

    # Traffic pace, expressed the way each motion law expresses it.
    # `waypoint`, `random_walk` and `sudden_stop` carry a `speed`;
    # `periodic` carries a `period`, and going faster there means a
    # *shorter* one — hence the reciprocal. Touching only `speed` would
    # have left the reference warehouse's forklift, which is periodic,
    # completely unperturbed on this axis while the report claimed the
    # axis was covered.
    obstacles = []
    for obstacle in environment.get("dynamic_obstacles", ()):
        entry = dict(obstacle)
        motion = dict(entry["motion"])
        if "speed" in motion:
            motion["speed"] = motion["speed"] * perturbation.traffic_speed
        if "period" in motion:
            motion["period"] = motion["period"] / perturbation.traffic_speed
            # HĐ-2 requires a periodic obstacle's seed offset to clear a
            # full cycle, or every seed meets it at the same phase and a
            # hundred episodes collapse to one distinct episode. The
            # offset therefore has to follow the period rather than stay
            # put: a lengthened cycle would otherwise overtake it and the
            # variant would be refused at load — turning "this profile is
            # fragile" into "this generator produced an invalid file".
            if entry.get("seed_time_offset"):
                entry["seed_time_offset"] = entry["seed_time_offset"] / perturbation.traffic_speed
        entry["motion"] = motion
        obstacles.append(entry)
    environment["dynamic_obstacles"] = obstacles
    payload["environment"] = environment

    return TaskProfile.model_validate(payload)


def neighborhood_variants(
    profile: TaskProfile, *, count: int = 20, seed: int = 0
) -> tuple[Variant, ...]:
    """``count`` structured what-ifs around one deployment (N5).

    Twenty by default, which is the topic document's proposal. It is a
    budget rather than a statistical requirement: each variant costs a
    full sweep, so this is the axis where "measure more" runs straight
    into hours of wall clock.

    A variant that the map cannot support is **not** silently dropped —
    it is returned like any other, and validating the missions against
    the map is the caller's job at the point where the map is loaded.
    Skipping them here would quietly shrink the denominator of
    ``robustness_margin``, which is the one number this module exists to
    produce.
    """
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, len(profile.id)])))
    variants = []
    for _ in range(count):
        perturbation = _perturbation(rng)
        variants.append(
            Variant(
                variant_id=sha256_short(
                    canonical_json(perturbation.as_payload()), length=_VARIANT_ID_LENGTH
                ),
                profile=_apply(profile, perturbation),
                perturbation=perturbation,
            )
        )
    return tuple(variants)


def recommendation_robustness(
    nominal_recommendation: str | None, per_variant: dict[str, str | None]
) -> float | None:
    """``R`` = the share of variants that recommend the same candidate.

    ``None`` when there is nothing to compare — no nominal
    recommendation, or no variant ran. HĐ-12 reads a null as *"not
    measured"*, which is the honest answer; returning ``1.0`` for an
    empty neighbourhood would report perfect robustness from no evidence.

    **A variant that produced no recommendation counts against R**, and
    that is deliberate rather than harsh: "under this much input error
    the field stops being rankable at all" is exactly the fragility the
    number is asked about. Dropping those would report the stability of
    the variants that happened to stay easy.
    """
    if nominal_recommendation is None or not per_variant:
        return None
    agreed = sum(1 for choice in per_variant.values() if choice == nominal_recommendation)
    return agreed / len(per_variant)
