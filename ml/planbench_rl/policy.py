"""PPO local planner: the ``astar+ppo`` benchmark stack.

A trained policy replaces DWA as the controller while A* still supplies
the global path (decision D13 — benchmarks compare stacks, and both
stacks share the same global planner so the comparison isolates the
controller).

Safety wrapper (spec section 13): the network's output is checked for
NaN/inf and clipped to the robot's limits before it becomes a command.
An unusable action falls back to a full stop and is reported through
``LocalPlanResult.failure_reason`` — never silently swallowed.

Loading a checkpoint verifies its observation and reward versions match
the code, because a policy trained on a different encoding would consume
garbage inputs while looking perfectly healthy.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict

from planbench_planning.common.local_base import LocalPlanner, LocalPlanResult
from planbench_rl.observation import OBSERVATION_VERSION, ObservationConfig, encode
from planbench_rl.rewards import REWARD_VERSION
from planbench_schemas.episode import Observation
from planbench_schemas.geometry import Point2D
from planbench_schemas.robot import RobotConfig, RobotState, SimAction


class ModelMetadata(BaseModel):
    """What must be known about a checkpoint to use it responsibly."""

    model_config = ConfigDict(frozen=True)

    model_id: str
    algorithm: str = "ppo"
    observation_version: str = OBSERVATION_VERSION
    reward_version: str = REWARD_VERSION
    total_timesteps: int = 0
    training_seed: int = 0
    curriculum: tuple[str, ...] = ()
    created_at: str = ""
    is_smoke_test: bool = False
    notes: str = ""

    @staticmethod
    def load(path: str | Path) -> ModelMetadata:
        return ModelMetadata.model_validate_json(Path(path).read_text())

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.model_dump(mode="json"), indent=2))


class VersionMismatch(RuntimeError):
    """The checkpoint was trained against a different observation/reward."""


class PPOLocalPlanner(LocalPlanner):
    """Deterministic evaluation of a trained PPO policy."""

    def __init__(
        self,
        model,  # stable_baselines3.PPO — untyped to keep SB3 an optional import
        metadata: ModelMetadata,
        observation_config: ObservationConfig | None = None,
        control_period: float = 0.1,
        deterministic: bool = True,
    ) -> None:
        self._model = model
        self._metadata = metadata
        self._observation_config = observation_config or ObservationConfig()
        self._control_period = control_period
        self._deterministic = deterministic
        self._robot: RobotConfig | None = None
        self._path: tuple[Point2D, ...] = ()
        self._lidar_max_range = 6.0

        if metadata.observation_version != self._observation_config.version:
            raise VersionMismatch(
                f"checkpoint uses observation {metadata.observation_version!r} but this "
                f"code encodes {self._observation_config.version!r}"
            )

    @property
    def name(self) -> str:
        return "ppo"

    @property
    def control_period(self) -> float:
        return self._control_period

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    def reset(self, global_path: Sequence[Point2D], robot: RobotConfig) -> None:
        if not global_path:
            raise ValueError("PPO planner requires a non-empty global path")
        self._path = tuple(global_path)
        self._robot = robot

    def set_lidar_max_range(self, max_range: float) -> None:
        """Match the scenario's sensor so normalization stays consistent."""
        self._lidar_max_range = max_range

    def compute(self, state: RobotState, observation: Observation) -> LocalPlanResult:
        if self._robot is None:
            raise RuntimeError("reset() must be called before compute()")
        started_at = time.perf_counter()
        robot = self._robot

        vector = encode(
            observation, self._path, robot, self._lidar_max_range, self._observation_config
        )
        raw, _ = self._model.predict(vector, deterministic=self._deterministic)
        array = np.asarray(raw, dtype=np.float64).reshape(-1)
        latency = time.perf_counter() - started_at

        if array.size < 2 or not np.all(np.isfinite(array)):
            return LocalPlanResult(
                action=SimAction(linear_velocity=0.0, angular_velocity=0.0),
                latency_seconds=latency,
                failure_reason=(
                    f"policy produced an unusable action {array.tolist()!r}; commanding stop"
                ),
            )

        normalized = np.clip(array[:2], -1.0, 1.0)
        linear = float(normalized[0]) * robot.max_linear_velocity
        angular = float(normalized[1]) * robot.max_angular_velocity
        if not (math.isfinite(linear) and math.isfinite(angular)):
            return LocalPlanResult(
                action=SimAction(linear_velocity=0.0, angular_velocity=0.0),
                latency_seconds=latency,
                failure_reason="denormalized action was not finite; commanding stop",
            )
        return LocalPlanResult(
            action=SimAction(linear_velocity=linear, angular_velocity=angular),
            latency_seconds=latency,
        )


def load_ppo_planner(
    model_path: str | Path,
    metadata_path: str | Path | None = None,
    *,
    deterministic: bool = True,
) -> PPOLocalPlanner:
    """Load a checkpoint plus its metadata sidecar.

    The sidecar is mandatory in spirit: without it there is no record of
    which observation/reward version produced the weights. A missing file
    is therefore an error, not a default.
    """
    from stable_baselines3 import PPO  # imported lazily: SB3 is optional

    model_path = Path(model_path)
    metadata_path = Path(metadata_path) if metadata_path else model_path.with_suffix(".json")
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"metadata sidecar {metadata_path} is missing; a checkpoint without its "
            "observation/reward version cannot be used safely"
        )
    metadata = ModelMetadata.load(metadata_path)
    model = PPO.load(str(model_path), device="cpu")
    return PPOLocalPlanner(model, metadata, deterministic=deterministic)
