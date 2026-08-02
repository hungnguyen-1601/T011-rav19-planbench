"""P01 hyperparameter-tuning results (read-only)."""

from __future__ import annotations

from fastapi import APIRouter

from planbench_api.auth import ActiveUser
from planbench_benchmark import TuningResult, load_tuning_cache

router = APIRouter(prefix="/tuning", tags=["tuning"])


@router.get("", response_model=dict[str, TuningResult])
def get_tuning_results(_: ActiveUser) -> dict[str, TuningResult]:
    """Cached Optuna search results per tunable stack.

    Empty until ``scripts/tune_hyperparameters.py`` has been run at
    least once — a missing cache is a "not yet tuned" state, not an
    error.
    """
    return load_tuning_cache()
