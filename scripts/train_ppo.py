#!/usr/bin/env python3
"""Train a PPO navigation policy.

Smoke run (validates the pipeline in a couple of minutes on CPU):

    PYTHONPATH= .venv/bin/python scripts/train_ppo.py --smoke

Real run (hours, and still only a starting point):

    PYTHONPATH= .venv/bin/python scripts/train_ppo.py \
        --model-id ppo-v1 --timesteps 2000000 \
        --curriculum open_space,static_obstacles,wide_corridor,doorway

A smoke checkpoint is marked ``is_smoke_test`` in its metadata: its
benchmark numbers describe the pipeline, not the algorithm.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "packages/schemas",
    "packages/planning",
    "packages/metrics",
    "packages/benchmark",
    "packages/explanation",
    "packages/plugin_sdk",
    "services/simulator",
    "services/tracking",
    "ml",
):
    sys.path.insert(0, str(REPO_ROOT / relative))

from planbench_rl.training import (  # noqa: E402
    PPOHyperparameters,
    TrainingConfig,
    evaluate,
    train,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a PlanBench PPO policy")
    parser.add_argument("--model-id", default="ppo-smoke")
    parser.add_argument("--timesteps", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--curriculum",
        default="open_space",
        help="Comma-separated library scenarios, easiest first.",
    )
    parser.add_argument("--n-steps", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-episode-steps", type=int, default=1500)
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "ml" / "checkpoints"))
    parser.add_argument("--mlflow-uri", default="")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Tiny run that only proves the pipeline works end to end.",
    )
    parser.add_argument("--eval-seeds", default="1,2,3")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.smoke:
        args.timesteps = min(args.timesteps, 4096)
        args.n_steps = min(args.n_steps, 512)
        args.batch_size = min(args.batch_size, 64)
        args.max_episode_steps = min(args.max_episode_steps, 300)

    curriculum = tuple(name.strip() for name in args.curriculum.split(",") if name.strip())
    config = TrainingConfig(
        model_id=args.model_id,
        total_timesteps=args.timesteps,
        seed=args.seed,
        curriculum=curriculum,
        max_episode_steps=args.max_episode_steps,
        hyperparameters=PPOHyperparameters(n_steps=args.n_steps, batch_size=args.batch_size),
        output_dir=args.output_dir,
        mlflow_tracking_uri=args.mlflow_uri,
        is_smoke_test=args.smoke,
    )

    print(
        f"training {config.model_id}: {config.total_timesteps} timesteps, "
        f"curriculum={list(curriculum)}, seed={config.seed}"
    )
    checkpoint, metadata = train(config)
    print(f"checkpoint: {checkpoint}")
    print(
        f"metadata:   observation={metadata.observation_version} "
        f"reward={metadata.reward_version} smoke={metadata.is_smoke_test}"
    )

    seeds = [int(value) for value in args.eval_seeds.split(",") if value.strip()]
    result = evaluate(
        checkpoint,
        list(curriculum),
        seeds,
        observation_config=config.observation,
        reward_config=config.reward,
        max_episode_steps=config.max_episode_steps,
    )
    print("\ndeterministic evaluation")
    print(f"  episodes        {result.episodes}")
    print(f"  success_rate    {result.success_rate:.2f}")
    print(f"  collision_rate  {result.collision_rate:.2f}")
    print(f"  mean_reward     {result.mean_reward:.1f}")
    print(f"  mean_steps      {result.mean_steps:.0f}")
    print(f"  invalid_actions {result.invalid_action_steps}")
    for name, rate in result.per_scenario.items():
        print(f"    {name:24s} success={rate:.2f}")
    if metadata.is_smoke_test:
        print(
            "\nNOTE: smoke checkpoint. These numbers validate the pipeline, "
            "not the quality PPO can reach."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
