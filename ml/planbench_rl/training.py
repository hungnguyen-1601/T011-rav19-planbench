"""PPO training and deterministic evaluation.

Curriculum (spec section 23): stages come from the scenario library's
``CURRICULUM_ORDER``, easiest first. Each stage trains on all scenarios
up to that difficulty, so the policy keeps practising what it already
learned instead of forgetting it.

Everything that defines a run — hyperparameters, observation version,
reward version, curriculum, seed — is logged to MLflow and written to
the checkpoint's metadata sidecar, because a model without that record
cannot be reproduced or safely reused.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from planbench_benchmark import CURRICULUM_ORDER, build_scenario
from planbench_rl.env import PlanBenchNavEnv
from planbench_rl.observation import ObservationConfig
from planbench_rl.policy import ModelMetadata
from planbench_rl.rewards import RewardConfig

logger = logging.getLogger("planbench.rl.training")


class PPOHyperparameters(BaseModel):
    """SB3 PPO settings. Logged verbatim with every run."""

    model_config = ConfigDict(frozen=True)

    learning_rate: float = 3e-4
    n_steps: int = 1024
    batch_size: int = 64
    n_epochs: int = 10
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.0
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    net_arch: tuple[int, ...] = (128, 128)


class TrainingConfig(BaseModel):
    """One training run end to end."""

    model_config = ConfigDict(frozen=True)

    model_id: str
    total_timesteps: int = Field(gt=0)
    seed: int = 0
    curriculum: tuple[str, ...] = ("open_space",)
    max_episode_steps: int = 1500
    hyperparameters: PPOHyperparameters = Field(default_factory=PPOHyperparameters)
    observation: ObservationConfig = Field(default_factory=ObservationConfig)
    reward: RewardConfig = Field(default_factory=RewardConfig)
    output_dir: str = "ml/checkpoints"
    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "planbench-ppo"
    is_smoke_test: bool = False


class EvaluationResult(BaseModel):
    """Deterministic evaluation over a set of scenarios and seeds."""

    model_config = ConfigDict(frozen=True)

    episodes: int
    success_rate: float
    collision_rate: float
    mean_reward: float
    mean_steps: float
    invalid_action_steps: int
    per_scenario: dict[str, float]


def curriculum_scenarios(stage: str) -> list[tuple]:
    """All library scenarios up to and including ``stage`` (easiest first)."""
    if stage not in CURRICULUM_ORDER:
        raise ValueError(f"unknown curriculum stage {stage!r}; expected one of {CURRICULUM_ORDER}")
    upto = CURRICULUM_ORDER[: CURRICULUM_ORDER.index(stage) + 1]
    return [build_scenario(name) for name in upto]


def make_env(config: TrainingConfig, stage: str) -> PlanBenchNavEnv:
    return PlanBenchNavEnv(
        curriculum_scenarios(stage),
        observation_config=config.observation,
        reward_config=config.reward,
        max_episode_steps=config.max_episode_steps,
    )


def train(config: TrainingConfig) -> tuple[str, ModelMetadata]:
    """Train through the curriculum; returns (checkpoint path, metadata).

    Timesteps are split evenly across stages. The same model continues
    into each stage — that is what makes it a curriculum rather than a
    series of unrelated runs.
    """
    from stable_baselines3 import PPO

    from planbench_tracking import build_tracker  # noqa: F401 - parity with benchmark tracking

    hyper = config.hyperparameters
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    per_stage = max(1, config.total_timesteps // len(config.curriculum))
    model = None
    for index, stage in enumerate(config.curriculum):
        env = make_env(config, stage)
        if model is None:
            model = PPO(
                "MlpPolicy",
                env,
                learning_rate=hyper.learning_rate,
                n_steps=hyper.n_steps,
                batch_size=hyper.batch_size,
                n_epochs=hyper.n_epochs,
                gamma=hyper.gamma,
                gae_lambda=hyper.gae_lambda,
                clip_range=hyper.clip_range,
                ent_coef=hyper.ent_coef,
                vf_coef=hyper.vf_coef,
                max_grad_norm=hyper.max_grad_norm,
                policy_kwargs={"net_arch": list(hyper.net_arch)},
                seed=config.seed,
                device="cpu",
                verbose=0,
            )
        else:
            model.set_env(env)
        logger.info(
            "curriculum stage started",
            extra={"context": {"stage": stage, "index": index, "timesteps": per_stage}},
        )
        model.learn(total_timesteps=per_stage, reset_num_timesteps=False, progress_bar=False)

    assert model is not None
    checkpoint = output_dir / f"{config.model_id}.zip"
    model.save(str(checkpoint))
    metadata = ModelMetadata(
        model_id=config.model_id,
        observation_version=config.observation.version,
        reward_version=config.reward.version,
        total_timesteps=config.total_timesteps,
        training_seed=config.seed,
        curriculum=config.curriculum,
        created_at=datetime.now(UTC).isoformat(),
        is_smoke_test=config.is_smoke_test,
        notes=(
            "SMOKE TEST — trained for a handful of timesteps to validate the "
            "pipeline. Not a production policy; its benchmark numbers say "
            "nothing about how good PPO can be."
            if config.is_smoke_test
            else ""
        ),
    )
    metadata.save(checkpoint.with_suffix(".json"))
    _log_to_mlflow(config, metadata, checkpoint)
    return str(checkpoint), metadata


def evaluate(
    model_path: str | Path,
    scenarios: list[str],
    seeds: list[int],
    observation_config: ObservationConfig | None = None,
    reward_config: RewardConfig | None = None,
    max_episode_steps: int = 1500,
) -> EvaluationResult:
    """Deterministic evaluation: no exploration noise, fixed seeds."""
    from stable_baselines3 import PPO

    model = PPO.load(str(model_path), device="cpu")
    observation_config = observation_config or ObservationConfig()
    successes = collisions = invalid = 0
    rewards: list[float] = []
    steps: list[int] = []
    per_scenario: dict[str, list[bool]] = {}

    for name in scenarios:
        env = PlanBenchNavEnv(
            [build_scenario(name)],
            observation_config=observation_config,
            reward_config=reward_config or RewardConfig(),
            max_episode_steps=max_episode_steps,
        )
        for seed in seeds:
            observation, _ = env.reset(seed=seed)
            total = 0.0
            info: dict = {}
            while True:
                action, _ = model.predict(observation, deterministic=True)
                observation, reward, terminated, truncated, info = env.step(action)
                total += reward
                if terminated or truncated:
                    break
            success = bool(info.get("is_success"))
            successes += int(success)
            collisions += int(info.get("status") == "collision")
            invalid += int(info.get("invalid_actions", 0))
            rewards.append(total)
            steps.append(int(info.get("steps", 0)))
            per_scenario.setdefault(name, []).append(success)

    episodes = len(rewards)
    return EvaluationResult(
        episodes=episodes,
        success_rate=successes / episodes if episodes else 0.0,
        collision_rate=collisions / episodes if episodes else 0.0,
        mean_reward=sum(rewards) / episodes if episodes else 0.0,
        mean_steps=sum(steps) / episodes if episodes else 0.0,
        invalid_action_steps=invalid,
        per_scenario={name: sum(results) / len(results) for name, results in per_scenario.items()},
    )


def _log_to_mlflow(config: TrainingConfig, metadata: ModelMetadata, checkpoint: Path) -> None:
    """Record the run; never let a tracking failure break training."""
    if not config.mlflow_tracking_uri:
        return
    try:
        import os

        if config.mlflow_tracking_uri.startswith("file:"):
            os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
        import mlflow

        mlflow.set_tracking_uri(config.mlflow_tracking_uri)
        mlflow.set_experiment(config.mlflow_experiment)
        with mlflow.start_run(run_name=config.model_id):
            mlflow.set_tags(
                {
                    "model_id": config.model_id,
                    "algorithm": "ppo",
                    "observation_version": metadata.observation_version,
                    "reward_version": metadata.reward_version,
                    "is_smoke_test": str(metadata.is_smoke_test),
                }
            )
            mlflow.log_params(
                {
                    "total_timesteps": config.total_timesteps,
                    "seed": config.seed,
                    "curriculum": list(config.curriculum),
                    "max_episode_steps": config.max_episode_steps,
                    **config.hyperparameters.model_dump(),
                    **{f"reward_{k}": v for k, v in config.reward.model_dump().items()},
                }
            )
            mlflow.log_metric("checkpoint_bytes", checkpoint.stat().st_size)
    except Exception as exc:  # noqa: BLE001 - tracking must never fail a run
        logger.warning(
            "MLflow logging skipped", extra={"context": {"error": f"{type(exc).__name__}: {exc}"}}
        )
