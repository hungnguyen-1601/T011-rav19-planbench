"""Shared TaskProfile fixtures for the decision-layer tests.

Every layer downstream of HĐ-2 reads its thresholds from a task profile —
gates, anchors, objectives, context generation — so the fixture lives here
rather than being copied into each test module. Following the existing
convention of ``tests/agent_fakes.py``.

The defaults mirror the contract's own warehouse example (HĐ-2.1), which
keeps the numbers in tests recognisable: 1% accepted collision risk means
``N_min`` is 300, and a 50 ms control period means G4's threshold is 50.
"""

from __future__ import annotations

import math

from planbench_schemas.task_profile import TaskProfile

#: One moving obstacle with a seed-derived clock offset, so episodes at
#: different seeds are genuinely different draws (see
#: ``EnvironmentSpec._validate_obstacles``).
TRAFFIC: list[dict[str, object]] = [
    {
        "name": "forklift",
        "radius": 0.4,
        # One full period. At 6.0 s the seeds explored a quarter of a
        # 24 s cycle — the flaw the reference warehouse shipped with.
        "seed_time_offset": 24.0,
        "motion": {
            "kind": "periodic",
            "start": {"x": 12.0, "y": 4.0},
            "end": {"x": 12.0, "y": 18.0},
            "period": 24.0,
        },
    }
]

#: The contract's own board budget (HĐ-2.4): 8 GB Jetson with the OS,
#: perception, localisation and logging already claimed, leaving 3277 MB
#: for navigation. Kept as one block so a test that needs a different
#: budget states which line it is changing.
HARDWARE: dict[str, object] = {
    "target_device": "jetson_orin_nano",
    "total_ram_mb": 8192,
    "ram_budget_breakdown": {
        "os_and_middleware_mb": 1536,
        "perception_stack_mb": 2048,
        "localization_mapping_mb": 819,
        "logging_and_reserve_mb": 512,
    },
    "available_ram_mb": 3277,
}

CONSTRAINTS: dict[str, object] = {
    "success_rate_min": 0.95,
    "collision_probability_max": 0.01,
    "goal_tolerance_m": 0.20,
    # Heading unconstrained. The platform has no final-orientation
    # controller, so a tighter value is refused at load — see the
    # reservation in CONTRACTS HĐ-6 and ``_heading_must_be_unconstrained``.
    "goal_tolerance_rad": math.pi,
    "episode_timeout_s": 180,
    "stuck_threshold_s": 10,
    "clearance_warning_m": 0.35,
}


def make_profile(**overrides: object) -> TaskProfile:
    """A valid single-mission warehouse profile; overrides patch fields."""
    payload: dict[str, object] = {
        "id": "warehouse_a_v1",
        "environment": {
            "map": "maps/warehouse_a.pgm",
            "map_yaml": "maps/warehouse_a.yaml",
            "dynamic_obstacles": [dict(obstacle) for obstacle in TRAFFIC],
        },
        "missions": [
            {"id": "m1", "start": [2.0, 3.0, 0.0], "goal": [38.0, 21.0, 1.57], "probability": 1.0}
        ],
        "robot": {
            "radius": 0.26,
            "max_linear_velocity": 0.8,
            "max_angular_velocity": 1.2,
            "max_linear_acceleration": 0.5,
            "max_angular_acceleration": 1.0,
            "control_period": 0.05,
        },
        "available_observations": ["lidar_2d"],
        "constraints": dict(CONSTRAINTS),
        "hardware": hardware(),
    }
    payload.update(overrides)
    return TaskProfile.model_validate(payload)


def three_missions() -> list[dict[str, object]]:
    """A mission distribution whose probabilities do not sum to exactly
    1.0 in binary floating point — the contract's own example."""
    return [
        {"id": "m1", "start": [0, 0, 0], "goal": [5, 5, 0], "probability": 0.40},
        {"id": "m2", "start": [0, 0, 0], "goal": [9, 1, 0], "probability": 0.35},
        {"id": "m3", "start": [5, 5, 0], "goal": [1, 8, 0], "probability": 0.25},
    ]


def constraints(**overrides: object) -> dict[str, object]:
    """Constraint block with fields replaced, for gate-threshold tests."""
    return {**CONSTRAINTS, **overrides}


def hardware(**overrides: object) -> dict[str, object]:
    """Hardware block with fields replaced, for G4/G5 threshold tests."""
    payload = {**HARDWARE, "ram_budget_breakdown": dict(HARDWARE["ram_budget_breakdown"])}  # type: ignore[arg-type]
    payload.update(overrides)
    return payload


def environment(**overrides: object) -> dict[str, object]:
    """Environment block with fields replaced, for traffic tests."""
    payload: dict[str, object] = {
        "map": "maps/warehouse_a.pgm",
        "map_yaml": "maps/warehouse_a.yaml",
        "dynamic_obstacles": [dict(obstacle) for obstacle in TRAFFIC],
    }
    payload.update(overrides)
    return payload
