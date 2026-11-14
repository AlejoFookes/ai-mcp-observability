from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from multimcp.models import SCHEMA_VERSION
from multimcp_api.schemas.common import ApiModel


class FinOpsRowOut(ApiModel):
    key: str
    request_count: int
    error_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    unpriced_count: int


class FinOpsSummaryResponse(ApiModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    currency: Literal["USD"] = "USD"
    rows: list[FinOpsRowOut]


class LatencyRowOut(ApiModel):
    key: str
    count: int
    p50_ms: float
    p95_ms: float
    error_rate: float


class LatencyResponse(ApiModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    rows: list[LatencyRowOut]


class TraceSpanOut(ApiModel):
    kind: Literal["genai", "mcp"]
    event_id: UUID
    occurred_at: datetime
    trace_id: str
    status: str
    latency_ms: float
    label: str
    detail: dict[str, Any] = Field(default_factory=dict)


class TraceResponse(ApiModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    trace_id: str
    spans: list[TraceSpanOut]


class CompareSideOut(ApiModel):
    key: str
    request_count: int
    error_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    unpriced_count: int
    p50_ms: float | None
    p95_ms: float | None
    error_rate: float


class CompareResponse(ApiModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    left: CompareSideOut
    right: CompareSideOut
