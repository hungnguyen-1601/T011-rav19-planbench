"""Observation vocabulary shared by candidates and deployments (G6).

Gate G6 is a set-subset test: a candidate's ``observation_requirements``
must be contained in the deployment's ``available_observations``
(CONTRACTS HĐ-7). That test is only trustworthy if both sides spell the
tokens the same way. A candidate that declares ``lidar2d`` against a
deployment offering ``lidar_2d`` would be eliminated for a typo, and the
Decision Card would report a hardware incompatibility that does not
exist — a wrong answer that looks like a correct one.

So the vocabulary is closed. Both sides validate against
:data:`KNOWN_OBSERVATIONS`, and an unknown token fails loudly at parse
time rather than quietly at gate time. Adding a sensor is one line here
plus its cost declaration on the deployment side.

**What belongs in this vocabulary, and what does not.** These tokens name
*runtime perception the deployment must own* — a sensor on the robot or a
perception subsystem producing estimates. The static occupancy map is not
one of them: the deployment supplies it in ``TaskProfile.environment``,
so every deployment has it by construction. Listing it as a requirement
would make every modular candidate fail G6 on a profile whose author did
not think to declare the obvious, which is the opposite of what the gate
is for. This is why the registry's ``full_static_map`` observation class
(P02) maps to *no* requirement token — see
``planbench_benchmark.candidates``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

#: Runtime perception a candidate may require and a deployment may own.
#:
#: - ``lidar_2d``: planar range returns. What the MVP simulator provides.
#: - ``human_state_estimates``: positions and velocities of the dynamic
#:   agents. Strictly more than any range sensor gives; a candidate that
#:   needs it is asking the deployment to own a tracking subsystem, which
#:   is the cost N6 exists to surface.
ObservationToken = Literal["lidar_2d", "human_state_estimates"]

KNOWN_OBSERVATIONS: tuple[ObservationToken, ...] = (
    "lidar_2d",
    "human_state_estimates",
)


class UnknownObservationError(ValueError):
    """A token outside :data:`KNOWN_OBSERVATIONS`."""


def canonical_observations(values: Iterable[str], *, field: str) -> tuple[ObservationToken, ...]:
    """Validate, deduplicate and sort observation tokens.

    Sorting is what makes two spellings of one set compare and hash
    equal, so it is done here rather than left to each caller: a
    candidate id derived from an unsorted tuple would depend on the order
    somebody typed the sensors in.

    ``field`` names the offending field in the error message; the person
    reading it is fixing a YAML file, not a stack trace.
    """
    cleaned = {value.strip() for value in values}
    unknown = sorted(cleaned - set(KNOWN_OBSERVATIONS))
    if unknown:
        raise UnknownObservationError(
            f"{field} contains unknown observation(s) {unknown}; "
            f"known observations are {list(KNOWN_OBSERVATIONS)}. "
            "Add the token to planbench_schemas.observations if the platform "
            "really models this sensor — do not spell it differently here, "
            "because gate G6 compares these tokens literally."
        )
    return tuple(sorted(cleaned))  # type: ignore[arg-type]
