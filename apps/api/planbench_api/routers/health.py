"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from planbench_api.config import get_settings
from planbench_api.schemas import DeploymentState, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Alive, which build, and under which rules.

    The deployment shape rides along because the banner that announces
    relaxed duties has to be up before anybody signs in — "this machine
    approves its own work" is context for reading the login page too.
    """
    settings = get_settings()
    policy = getattr(request.app.state, "deployment", None)
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.version,
        deployment=(
            None
            if policy is None
            else DeploymentState(
                profile=policy.profile.value,
                separation_of_duties=policy.separation_of_duties.value,
            )
        ),
    )
