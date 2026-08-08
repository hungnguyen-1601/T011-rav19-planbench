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

from planbench_schemas.task_profile import TaskProfile

CONSTRAINTS: dict[str, object] = {
    "success_rate_min": 0.95,
    "collision_probability_max": 0.01,
    "goal_tolerance_m": 0.20,
    "goal_tolerance_rad": 0.35,
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
        "hardware": {"target_device": "jetson_orin_nano", "available_ram_mb": 2048},
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
