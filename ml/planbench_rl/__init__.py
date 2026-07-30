"""PlanBench reinforcement learning: Gym environment, rewards, PPO stack.

Kept out of the core packages: the simulator must never depend on an RL
framework. This package adapts the core to Gymnasium and Stable-Baselines3.
"""

from planbench_rl.env import PlanBenchNavEnv
from planbench_rl.observation import OBSERVATION_VERSION, ObservationConfig, encode
from planbench_rl.rewards import REWARD_VERSION, RewardConfig, step_reward

__all__ = [
    "OBSERVATION_VERSION",
    "REWARD_VERSION",
    "ObservationConfig",
    "PlanBenchNavEnv",
    "RewardConfig",
    "encode",
    "step_reward",
]
