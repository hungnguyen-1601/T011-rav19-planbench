"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from planbench_api.config import get_settings
from planbench_api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", app=settings.app_name, version=settings.version)
