"""Ingest GenAI and MCP event batches (SPEC §6.3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from multimcp_api.auth import require_ingest_token
from multimcp_api.deps import enforce_ingest_body_limit, get_repository
from multimcp_api.repositories.base import EventRepository
from multimcp_api.schemas.common import IngestResponse
from multimcp_api.schemas.ingest import GenAIIngestRequest, McpIngestRequest

router = APIRouter(
    tags=["ingest"],
    dependencies=[Depends(require_ingest_token), Depends(enforce_ingest_body_limit)],
)


@router.post("/events", response_model=IngestResponse)
async def post_events(
    payload: GenAIIngestRequest,
    repository: Annotated[EventRepository, Depends(get_repository)],
) -> IngestResponse:
    result = await repository.insert_genai(payload.events)
    return IngestResponse(accepted=result.accepted, duplicates=result.duplicates)


@router.post("/mcp-events", response_model=IngestResponse)
async def post_mcp_events(
    payload: McpIngestRequest,
    repository: Annotated[EventRepository, Depends(get_repository)],
) -> IngestResponse:
    result = await repository.insert_mcp(payload.events)
    return IngestResponse(accepted=result.accepted, duplicates=result.duplicates)
