"""Experiment tracking adapters (MLflow and a no-op default).

Tracking is infrastructure, so it lives outside the core packages: the
benchmark engine returns a report and knows nothing about MLflow.
"""

from planbench_tracking.base import ExperimentTracker, NullTracker, TrackedRun
from planbench_tracking.mlflow_tracker import MLflowTracker, build_tracker

__all__ = [
    "ExperimentTracker",
    "MLflowTracker",
    "NullTracker",
    "TrackedRun",
    "build_tracker",
]
