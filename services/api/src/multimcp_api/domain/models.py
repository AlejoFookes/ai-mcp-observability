"""Query and row types for EventRepository (SPEC §6.3 / §6.4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

FinOpsGroupBy = Literal["model", "provider", "prompt_version", "mcp_server"]
LatencyGroupBy = Literal["model", "operation", "mcp_tool"]
CompareDimension = Literal["prompt_version", "model"]
EvalStatus = Literal["queued", "running", "succeeded", "failed"]
HallucinationLabel = Literal["supported", "partial", "unsupported"]
TraceKind = Literal["genai", "mcp"]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InsertResult(DomainModel):
    accepted: int = Field(ge=0)
    duplicates: int = Field(ge=0)


class WindowQuery(DomainModel):
    start: datetime = Field(alias="from")
    end: datetime = Field(alias="to")
    group_by: str
    include_judge: bool = False

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class FinOpsRow(DomainModel):
    key: str
    request_count: int = 0
    error_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: Decimal = Decimal("0")
    unpriced_count: int = 0


class LatencyRow(DomainModel):
    key: str
    count: int
    p50_ms: float
    p95_ms: float
    error_rate: float


class TraceSpan(DomainModel):
    kind: TraceKind
    event_id: UUID
    occurred_at: datetime
    trace_id: str
    status: str
    latency_ms: float
    label: str
    detail: dict[str, Any] = Field(default_factory=dict)


class CompareQuery(DomainModel):
    start: datetime = Field(alias="from")
    end: datetime = Field(alias="to")
    dimension: CompareDimension
    left: str
    right: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class CompareSide(DomainModel):
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


class CompareResult(DomainModel):
    left: CompareSide
    right: CompareSide


class EvalJob(DomainModel):
    job_id: UUID = Field(default_factory=uuid4)
    schema_version: Literal["1.0"] = "1.0"
    status: EvalStatus = "queued"
    rubric_version: str
    judge_model: str | None = None
    trace_id: str | None = None
    query: str
    contexts: list[str]
    answer: str
    context_relevance: float | None = None
    hallucination_label: HallucinationLabel | None = None
    rationale: str | None = None
    error_message: str | None = None
    attempt: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    locked_at: datetime | None = None


class EvalOutcome(DomainModel):
    status: Literal["succeeded", "failed"]
    context_relevance: float | None = None
    hallucination_label: HallucinationLabel | None = None
    rationale: str | None = None
    error_message: str | None = None
    judge_model: str | None = None
