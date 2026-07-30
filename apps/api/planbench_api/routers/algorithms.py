"""Algorithm registry endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from planbench_api.services import algorithms_catalogue
from planbench_benchmark import AlgorithmInfo

router = APIRouter(prefix="/algorithms", tags=["algorithms"])


@router.get("", response_model=list[AlgorithmInfo])
def get_algorithms() -> list[AlgorithmInfo]:
    """Registered navigation stacks.

    ``benchmarkable=False`` marks reference stacks that exist only to
    validate the pipeline and must not be used for conclusions.
    """
    return algorithms_catalogue()


@router.get("/{algorithm_id}", response_model=AlgorithmInfo)
def get_algorithm(algorithm_id: str) -> AlgorithmInfo:
    from planbench_benchmark.registry import UnknownAlgorithmError

    for info in algorithms_catalogue():
        if info.id == algorithm_id:
            return info
    raise UnknownAlgorithmError(f"unknown algorithm {algorithm_id!r}")
