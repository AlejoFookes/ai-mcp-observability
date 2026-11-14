from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from multimcp_api.deps import get_app_settings, get_health_probe
from multimcp_api.errors import AppError
from multimcp_api.health import HealthProbe
from multimcp_api.schemas.common import HealthResponse
from multimcp_api.settings import Settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: Annotated[Settings, Depends(get_app_settings)],
    probe: Annotated[HealthProbe, Depends(get_health_probe)],
    ready: Annotated[bool, Query()] = False,
) -> HealthResponse:
    """Liveness always 200. `ready=true` is strict: 503 if storage ping fails."""
    ok = await probe.ping()
    if ready and not ok:
        raise AppError(503, "storage_unavailable", "storage backend is not ready")
    return HealthResponse(
        status="ok" if ok else "degraded",
        storage_backend=settings.storage_backend,
    )
