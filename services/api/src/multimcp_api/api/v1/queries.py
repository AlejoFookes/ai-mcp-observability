"""FinOps, latency, traces and compare endpoints (SPEC §6.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from multimcp_api.api.v1.window import validate_window
from multimcp_api.auth import require_ingest_token
from multimcp_api.deps import get_repository
from multimcp_api.domain.models import CompareQuery, WindowQuery
from multimcp_api.errors import AppError
from multimcp_api.repositories.base import EventRepository
from multimcp_api.schemas.queries import (
    CompareResponse,
    CompareSideOut,
    FinOpsRowOut,
    FinOpsSummaryResponse,
    LatencyResponse,
    LatencyRowOut,
    TraceResponse,
    TraceSpanOut,
)

router = APIRouter(tags=["queries"], dependencies=[Depends(require_ingest_token)])


@router.get("/finops/summary", response_model=FinOpsSummaryResponse)
async def finops_summary(
    repository: Annotated[EventRepository, Depends(get_repository)],
    from_: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
    group_by: Annotated[
        Literal["model", "provider", "prompt_version", "mcp_server"], Query()
    ] = "model",
    include_judge: Annotated[bool, Query()] = False,
) -> FinOpsSummaryResponse:
    validate_window(from_, to)
    rows = await repository.finops_summary(
        WindowQuery.model_validate(
            {
                "from": from_,
                "to": to,
                "group_by": group_by,
                "include_judge": include_judge,
            }
        )
    )
    return FinOpsSummaryResponse(
        rows=[FinOpsRowOut.model_validate(row.model_dump()) for row in rows]
    )


@router.get("/latency", response_model=LatencyResponse)
async def latency(
    repository: Annotated[EventRepository, Depends(get_repository)],
    from_: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
    group_by: Annotated[Literal["model", "operation", "mcp_tool"], Query()] = "model",
) -> LatencyResponse:
    validate_window(from_, to)
    rows = await repository.latency(
        WindowQuery.model_validate({"from": from_, "to": to, "group_by": group_by})
    )
    return LatencyResponse(
        rows=[LatencyRowOut.model_validate(row.model_dump()) for row in rows]
    )


@router.get("/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: str,
    repository: Annotated[EventRepository, Depends(get_repository)],
) -> TraceResponse:
    spans = await repository.get_trace(trace_id)
    if not spans:
        raise AppError(404, "not_found", f"trace {trace_id!r} not found")
    return TraceResponse(
        trace_id=trace_id,
        spans=[TraceSpanOut.model_validate(span.model_dump()) for span in spans],
    )


@router.get("/compare", response_model=CompareResponse)
async def compare(
    repository: Annotated[EventRepository, Depends(get_repository)],
    from_: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
    dimension: Annotated[Literal["prompt_version", "model"], Query()],
    left: Annotated[str, Query(min_length=1)],
    right: Annotated[str, Query(min_length=1)],
) -> CompareResponse:
    validate_window(from_, to)
    result = await repository.compare(
        CompareQuery.model_validate(
            {
                "from": from_,
                "to": to,
                "dimension": dimension,
                "left": left,
                "right": right,
            }
        )
    )
    return CompareResponse(
        left=CompareSideOut.model_validate(result.left.model_dump()),
        right=CompareSideOut.model_validate(result.right.model_dump()),
    )
