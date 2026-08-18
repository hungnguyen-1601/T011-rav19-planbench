"""What a plugin hands back (plan §5.5).

A refusal is data, not an exception: ``success=False`` with a reason for
a global plan, a ``failure_reason`` on a step. Exceptions crossing the
plugin boundary are a crash, and the host's job for crashes is
``safe_stop`` — never interpretation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GlobalPlanResponse(BaseModel):
    """A path, or the statement that none exists."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    success: bool
    path: tuple[tuple[float, float], ...] = ()
    failure_reason: str = ""
    #: Structure counts for HĐ-7.3 accounting (search vs tree nodes is
    #: the registry's classification, not the plugin's claim).
    expanded_nodes: int = Field(default=0, ge=0)


class LocalStepResponse(BaseModel):
    """One command, plus what benchmarks record about producing it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    linear_velocity: float
    angular_velocity: float
    predicted_trajectory: tuple[tuple[float, float], ...] = ()
    cost_components: dict[str, float] = Field(default_factory=dict)
    failure_reason: str = ""
    #: Self-reported compute time. Diagnostic on external runtimes —
    #: never the number a gate reads (plan §5.9 rule 6).
    reported_compute_ms: float | None = None
