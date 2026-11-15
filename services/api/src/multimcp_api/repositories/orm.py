"""SQLAlchemy table metadata matching SPEC §7."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

metadata = MetaData()


class Base(DeclarativeBase):
    metadata = metadata


class GenAIEventRow(Base):
    __tablename__ = "genai_events"
    __table_args__ = (
        CheckConstraint("price_status IN ('priced', 'unpriced')", name="genai_price_status"),
        CheckConstraint("status IN ('ok', 'error')", name="genai_status"),
    )

    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    environment: Mapped[str] = mapped_column(Text, nullable=False)
    sdk_name: Mapped[str] = mapped_column(Text, nullable=False)
    sdk_version: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    span_id: Mapped[str] = mapped_column(Text, nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer)
    ttft_ms: Mapped[float | None] = mapped_column(Double)
    latency_ms: Mapped[float] = mapped_column(Double, nullable=False)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    catalog_version: Mapped[str | None] = mapped_column(Text)
    price_status: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class McpEventRow(Base):
    __tablename__ = "mcp_events"
    __table_args__ = (
        CheckConstraint(
            "transport IN ('stdio', 'streamable_http')", name="mcp_transport"
        ),
        CheckConstraint("status IN ('ok', 'error')", name="mcp_status"),
    )

    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    environment: Mapped[str] = mapped_column(Text, nullable=False)
    server_name: Mapped[str] = mapped_column(Text, nullable=False)
    transport: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(Text)
    jsonrpc_id: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[float] = mapped_column(Double, nullable=False)
    payload_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[int | None] = mapped_column(Integer)
    error_type: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)


class EvalJobRow(Base):
    __tablename__ = "eval_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="eval_status",
        ),
        CheckConstraint(
            "hallucination_label IS NULL OR hallucination_label IN "
            "('supported', 'partial', 'unsupported')",
            name="eval_label",
        ),
        PrimaryKeyConstraint("job_id"),
    )

    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_version: Mapped[str] = mapped_column(Text, nullable=False)
    judge_model: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(Text)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    contexts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    context_relevance: Mapped[float | None] = mapped_column(Double)
    hallucination_label: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
