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
ObservationClass = Literal[
    "full_static_map",
    "lidar_only",
    "human_states",
    "lidar+human_states",
]

OBSERVATION_CLASSES: tuple[ObservationClass, ...] = (
    "full_static_map",
    "lidar_only",
    "human_states",
    "lidar+human_states",
)
