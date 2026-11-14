"""Ingest stubs for M3.1. Persistence arrives in M3.2 / M3.3."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from multimcp_api.auth import require_ingest_token
from multimcp_api.schemas.common import IngestResponse

router = APIRouter(tags=["ingest"], dependencies=[Depends(require_ingest_token)])


@router.post("/events", response_model=IngestResponse)
async def post_events() -> IngestResponse:
    return IngestResponse(accepted=0, duplicates=0)


@router.post("/mcp-events", response_model=IngestResponse)
async def post_mcp_events() -> IngestResponse:
    return IngestResponse(accepted=0, duplicates=0)
