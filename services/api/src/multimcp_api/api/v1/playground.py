from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from multimcp_api.auth import require_ingest_token
from multimcp_api.deps import get_app_settings, get_repository
from multimcp_api.playground.dual import run_dual_completion
from multimcp_api.repositories.base import EventRepository
from multimcp_api.schemas.playground import (
    DualPlaygroundRequest,
    DualPlaygroundResponse,
    DualSideOut,
)
from multimcp_api.settings import Settings

router = APIRouter(tags=["playground"], dependencies=[Depends(require_ingest_token)])


@router.post("/playground/dual", response_model=DualPlaygroundResponse)
async def playground_dual(
    body: DualPlaygroundRequest,
    settings: Annotated[Settings, Depends(get_app_settings)],
    repository: Annotated[EventRepository, Depends(get_repository)],
) -> DualPlaygroundResponse:
    """Run one prompt on two models; telemetry is written in-process to the repository."""
    result = await run_dual_completion(
        settings,
        repository,
        prompt=body.prompt,
        left_model=body.left_model,
        right_model=body.right_model,
        prompt_version=body.prompt_version,
    )
    return DualPlaygroundResponse(
        trace_id=result.trace_id,
        prompt_version=result.prompt_version,
        left=DualSideOut(
            model=result.left.model,
            answer=result.left.answer,
            latency_ms=result.left.latency_ms,
        ),
        right=DualSideOut(
            model=result.right.model,
            answer=result.right.answer,
            latency_ms=result.right.latency_ms,
        ),
    )
