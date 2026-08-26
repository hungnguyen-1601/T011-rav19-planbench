"""MLflow tracker: one MLflow run per (benchmark, algorithm).

Logged per algorithm run:

- params: algorithm id and config, seeds, fairness identity (map and
  scenario checksums, timeout, dt, robot limits, LiDAR config);
- metrics: the aggregate plus every per-seed metric, so a run can be
  compared across benchmarks and drilled into per seed;
- tags: benchmark id, conditions checksum, spec version.

The conditions checksum is the key to fair comparison in MLflow: two
runs with the same checksum faced identical conditions.
"""

from __future__ import annotations

import logging
import os

from planbench_benchmark import AlgorithmAggregate, BenchmarkReport
from planbench_tracking.base import ExperimentTracker, NullTracker, TrackedRun

logger = logging.getLogger("planbench.tracking")


class MLflowTracker(ExperimentTracker):
    """Log benchmark results to an MLflow tracking server or local store."""

    def __init__(self, tracking_uri: str, experiment: str = "planbench") -> None:
        # MLflow 3 refuses filesystem tracking stores unless the caller
        # opts in. A local file store is exactly the right choice for
        # development; production points at an MLflow server over http,
        # where this flag is irrelevant.
        if tracking_uri.startswith("file:") or tracking_uri.startswith("./"):
            os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

        import mlflow  # imported lazily: MLflow is optional infrastructure

        self._mlflow = mlflow
        self._tracking_uri = tracking_uri
        self._experiment = experiment
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)

    def log_benchmark(
        self,
        benchmark_id: str,
        report: BenchmarkReport,
        extra_tags: dict[str, str] | None = None,
    ) -> TrackedRun:
        mlflow = self._mlflow
        last_run_id = ""
        fairness = report.fairness
        for aggregate in report.aggregates:
            algorithm_spec = next(
                spec for spec in report.spec.algorithms if spec.id == aggregate.algorithm
            )
            run_name = f"{report.spec.name}:{aggregate.algorithm}"
            with mlflow.start_run(run_name=run_name) as run:
                mlflow.set_tags(
                    {
                        "benchmark_id": benchmark_id,
                        "benchmark_name": report.spec.name,
                        "algorithm": aggregate.algorithm,
                        "conditions_checksum": fairness.conditions_checksum,
                        "spec_version": report.spec.spec_version,
                        "map_checksum": fairness.map_checksum,
                        "scenario_checksum": fairness.scenario_checksum,
                        **(extra_tags or {}),
                    }
                )
                mlflow.log_params(
                    {
                        "algorithm": aggregate.algorithm,
                        "seeds": list(report.spec.seeds),
                        "map_name": fairness.map_name,
                        "scenario_name": fairness.scenario_name,
                        "timeout_seconds": fairness.timeout_seconds,
                        "simulation_dt": fairness.simulation_dt,
                        "robot_radius": fairness.robot_radius,
                        "max_linear_velocity": fairness.max_linear_velocity,
                        "max_angular_velocity": fairness.max_angular_velocity,
                        "lidar_num_rays": fairness.lidar_num_rays,
                        "lidar_max_range": fairness.lidar_max_range,
                        **{f"cfg_{k}": v for k, v in algorithm_spec.config.items()},
                    }
                )
                mlflow.log_metrics(_aggregate_metrics(aggregate))
                for record in report.runs:
                    if record.algorithm != aggregate.algorithm:
                        continue
                    for name, value in _run_metrics(record.metrics).items():
                        # step = seed keeps per-seed values addressable.
                        mlflow.log_metric(name, value, step=record.seed)
                last_run_id = run.info.run_id
        logger.info(
            "benchmark logged to MLflow",
            extra={
                "context": {
                    "benchmark_id": benchmark_id,
                    "experiment": self._experiment,
                    "algorithms": len(report.aggregates),
                }
            },
        )
        return TrackedRun(
            backend="mlflow",
            experiment=self._experiment,
            run_id=last_run_id,
            url=self._tracking_uri,
        )


def _aggregate_metrics(aggregate: AlgorithmAggregate) -> dict[str, float]:
    values = {
        "episodes": float(aggregate.episodes),
        "success_rate": aggregate.success_rate,
        "collision_rate": aggregate.collision_rate,
        "timeout_rate": aggregate.timeout_rate,
        "stuck_rate": aggregate.stuck_rate,
        "no_progress_rate": aggregate.no_progress_rate,
        "no_global_path_rate": aggregate.no_global_path_rate,
    }
    optional = {
        "mean_travel_time_successful": aggregate.mean_travel_time_successful,
        "mean_trajectory_length_successful": aggregate.mean_trajectory_length_successful,
        "mean_path_efficiency_successful": aggregate.mean_path_efficiency_successful,
        "mean_smoothness_successful": aggregate.mean_smoothness_successful,
        "mean_min_clearance": aggregate.mean_min_clearance,
        "worst_min_clearance": aggregate.worst_min_clearance,
        "mean_local_planning_latency": aggregate.mean_local_planning_latency,
        "max_local_planning_latency": aggregate.max_local_planning_latency,
        "mean_global_planning_time": aggregate.mean_global_planning_time,
    }
    values.update({name: value for name, value in optional.items() if value is not None})
    return values


def _run_metrics(metrics) -> dict[str, float]:  # noqa: ANN001 - EpisodeMetrics
    values = {
        "seed_travel_time": metrics.travel_time,
        "seed_trajectory_length": metrics.trajectory_length,
        "seed_average_speed": metrics.average_speed,
        "seed_smoothness": metrics.smoothness,
        "seed_success": 1.0 if metrics.success else 0.0,
        "seed_collision": 1.0 if metrics.collision else 0.0,
    }
    if metrics.min_clearance is not None:
        values["seed_min_clearance"] = metrics.min_clearance
    if metrics.path_efficiency is not None:
        values["seed_path_efficiency"] = metrics.path_efficiency
    return values


def build_tracker(tracking_uri: str, experiment: str = "planbench") -> ExperimentTracker:
    """Return an MLflow tracker, or a null tracker when unconfigured.

    A missing URI is a normal development setup, not an error. An MLflow
    import failure is logged and degraded to null tracking so a benchmark
    never fails because of the tracking backend.
    """
    if not tracking_uri:
        return NullTracker()
    try:
        return MLflowTracker(tracking_uri, experiment)
    except Exception as exc:  # noqa: BLE001 - tracking must never break a run
        logger.warning(
            "MLflow unavailable, falling back to null tracking",
            extra={"context": {"tracking_uri": tracking_uri, "error": str(exc)}},
        )
        return NullTracker()
