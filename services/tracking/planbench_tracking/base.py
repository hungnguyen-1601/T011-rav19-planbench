"""Tracker interface: what PlanBench records for every benchmark."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

from planbench_benchmark import BenchmarkReport


class TrackedRun(BaseModel):
    """Reference to the tracking backend's record of a benchmark."""

    model_config = ConfigDict(frozen=True)

    backend: str
    experiment: str = ""
    run_id: str = ""
    url: str = ""


class ExperimentTracker(ABC):
    """Records benchmark metadata, parameters and metrics."""

    @abstractmethod
    def log_benchmark(
        self,
        benchmark_id: str,
        report: BenchmarkReport,
        extra_tags: dict[str, str] | None = None,
    ) -> TrackedRun:
        """Record one benchmark; returns a reference to the stored run."""


class NullTracker(ExperimentTracker):
    """Default: records nothing. Keeps tracking optional in dev and tests."""

    def log_benchmark(
        self,
        benchmark_id: str,
        report: BenchmarkReport,
        extra_tags: dict[str, str] | None = None,
    ) -> TrackedRun:
        return TrackedRun(backend="null")
