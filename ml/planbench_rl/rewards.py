"""Versioned reward functions for the PlanBench navigation task.

The reward version is recorded with every trained model (spec section
24): changing these numbers changes what "good" means, so a policy
trained under v1 is not comparable to one trained under v2 unless the
reward is reported alongside.

Design rules:
- Terminal outcomes dominate: reaching the goal must outweigh any
  accumulation of shaping reward, otherwise a policy learns to farm
  shaping instead of finishing.
- Shaping is potential-based on goal *progress* (distance closed this
  step), which does not change the optimal policy, only the learning
  speed.
- Penalties name a specific bad behaviour; none of them is a catch-all.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planbench_schemas.episode import EpisodeStatus

REWARD_VERSION = "v1"


class RewardConfig(BaseModel):
    """Reward weights. Persisted with the model as hyperparameters."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    version: str = REWARD_VERSION

    # Terminal
    goal_reached: float = Field(default=200.0, description="One-off reward for reaching the goal.")
    collision: float = Field(default=-200.0, description="One-off penalty for any collision.")
    timeout: float = Field(default=-50.0)
    stuck: float = Field(default=-50.0)
    no_progress: float = Field(default=-50.0)

    # Per-step shaping
    progress: float = Field(
        default=30.0, description="Multiplies metres of goal distance closed this step."
    )
    time_penalty: float = Field(default=-0.05, description="Per-step cost, encourages speed.")
    path_tracking: float = Field(
        default=-0.5, description="Multiplies metres of deviation from the global path."
    )
    clearance_penalty: float = Field(
        default=-2.0, description="Applied when clearance drops below clearance_threshold."
    )
    clearance_threshold: float = Field(default=0.35, gt=0)
    oscillation_penalty: float = Field(
        default=-0.5, description="Applied when angular velocity flips sign."
    )
    control_effort: float = Field(
        default=-0.02, description="Multiplies |omega|, discourages needless spinning."
    )
    reverse_penalty: float = Field(default=-0.5, description="Multiplies |v| when v < 0.")


TERMINAL_REWARDS: dict[EpisodeStatus, str] = {
    EpisodeStatus.SUCCESS: "goal_reached",
    EpisodeStatus.COLLISION: "collision",
    EpisodeStatus.TIMEOUT: "timeout",
    EpisodeStatus.STUCK: "stuck",
    EpisodeStatus.NO_PROGRESS: "no_progress",
}


class RewardBreakdown(BaseModel):
    """Per-component reward for one step — logged for debugging training."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    total: float
    components: dict[str, float]


def step_reward(
    config: RewardConfig,
    *,
    progress_metres: float,
    path_deviation: float,
    clearance: float,
    linear_velocity: float,
    angular_velocity: float,
    previous_angular_velocity: float,
    status: EpisodeStatus,
) -> RewardBreakdown:
    """Reward for one simulation step, including any terminal bonus.

    ``progress_metres`` is positive when the robot moved closer to the
    goal this step.
    """
    components: dict[str, float] = {
        "progress": config.progress * progress_metres,
        "time": config.time_penalty,
        "path_tracking": config.path_tracking * abs(path_deviation),
        "control_effort": config.control_effort * abs(angular_velocity),
    }
    if clearance < config.clearance_threshold:
        # Scale with how far inside the threshold we are: grazing an
        # obstacle should hurt more than merely approaching one.
        deficit = (config.clearance_threshold - clearance) / config.clearance_threshold
        components["clearance"] = config.clearance_penalty * deficit
    if angular_velocity * previous_angular_velocity < 0:
        components["oscillation"] = config.oscillation_penalty
    if linear_velocity < 0:
        components["reverse"] = config.reverse_penalty * abs(linear_velocity)

    terminal_field = TERMINAL_REWARDS.get(status)
    if terminal_field is not None:
        components["terminal"] = getattr(config, terminal_field)

    return RewardBreakdown(total=sum(components.values()), components=components)
