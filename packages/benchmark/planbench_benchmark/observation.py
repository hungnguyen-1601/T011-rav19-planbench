"""Information parity: what each half of a stack is allowed to see (P02).

A benchmark only compares algorithms fairly when they were shown the
same thing. A planner that reads ground-truth pedestrian states is
solving an easier problem than one that only gets LiDAR returns, and a
leaderboard that ranks the two side by side reports that easier problem
as a better algorithm.

The platform cannot police this by inspection — a planner is arbitrary
code — so it does the next best thing: every registered stack *declares*
what it sees, the declaration travels with the results, and the
leaderboard refuses to rank different declarations together by default.

The two halves of a stack see different things, so a single label would
be a lie: a global planner is handed the full static map (that is what
"global" means), while the controller under it runs on sensing alone.
Hence two fields, one per layer.
"""

from __future__ import annotations

from typing import Literal

#: What a planner layer is given.
#:
#: - ``full_static_map``: the whole occupancy grid, obstacles included.
#:   Normal for a global planner; on a *local* planner it means the
#:   controller is cheating relative to a sensing-only one.
#: - ``lidar_only``: range returns plus own state, nothing else.
#: - ``human_states``: ground-truth positions/velocities of the dynamic
#:   agents. Strictly more information than any sensor gives.
#: - ``lidar+human_states``: both of the above.
#: - ``full_static_map+human_states``: the occupancy grid *and* the
#:   ground-truth dynamic agents. This is what a global planner is given
#:   the moment replanning is on — see :func:`global_class_under_replanning`.
ObservationClass = Literal[
    "full_static_map",
    "lidar_only",
    "human_states",
    "lidar+human_states",
    "full_static_map+human_states",
]

OBSERVATION_CLASSES: tuple[ObservationClass, ...] = (
    "full_static_map",
    "lidar_only",
    "human_states",
    "lidar+human_states",
    "full_static_map+human_states",
)

#: What a stack that declares ``full_static_map`` actually sees once it is
#: allowed to replan. Kept as a table rather than string concatenation so
#: an unforeseen declaration fails loudly instead of inventing a class
#: name that nothing else in the platform recognises.
_UNDER_REPLANNING: dict[ObservationClass, ObservationClass] = {
    "full_static_map": "full_static_map+human_states",
    "human_states": "human_states",
    "lidar_only": "lidar+human_states",
    "lidar+human_states": "lidar+human_states",
    "full_static_map+human_states": "full_static_map+human_states",
}


def global_class_under_replanning(
    declared: ObservationClass | None, *, replanning_enabled: bool
) -> ObservationClass | None:
    """The global planner's observation class *for one particular run*.

    The registry declaration is static — it is attached to a stack id —
    but what the global planner sees is not. With replanning off it plans
    once, before the episode starts, on a grid holding only the static
    obstacles: the declaration is exactly right. With replanning on it is
    handed ``engine.dynamic_obstacles_now()``, the ground-truth positions
    of the moving agents, which no sensor would have given it.

    Leaving the declaration alone in that second case would repeat the
    flaw this platform exists to expose (Alyassi et al., gap S1): a
    privileged planner ranked beside a sensing-only one under a label
    that says they saw the same thing. So the class is *derived* here,
    from the run conditions, and the derived value is what gets
    snapshotted into the report.

    ``None`` in, ``None`` out: a stack with no declaration has nothing to
    upgrade, and inventing one would be the fabrication the nullable
    field exists to prevent.
    """
    if declared is None or not replanning_enabled:
        return declared
    return _UNDER_REPLANNING[declared]
