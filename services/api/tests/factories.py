from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from multimcp.models import GenAIEvent, McpEvent


def make_genai(
    *,
    model: str = "gpt-4.1-mini",
    provider: str = "openai",
    prompt_version: str | None = "v1",
    latency_ms: float = 100.0,
    status: str = "ok",
    price_status: str = "priced",
    cost: str = "0.001",
    input_tokens: int = 10,
    output_tokens: int = 5,
    occurred_at: datetime | None = None,
    trace_id: str | None = None,
    metadata: dict | None = None,
    operation: str = "responses.create",
) -> GenAIEvent:
    return GenAIEvent(
        event_id=uuid4(),
        occurred_at=occurred_at or datetime(2026, 11, 14, 12, 0, tzinfo=UTC),
        environment="local",
        provider=provider,  # type: ignore[arg-type]
        model=model,
        operation=operation,  # type: ignore[arg-type]
        prompt_version=prompt_version,
        trace_id=trace_id or str(uuid4()),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=Decimal(cost) if price_status == "priced" else None,
        catalog_version="2026-11-01" if price_status == "priced" else None,
        price_status=price_status,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        error_type="APIError" if status == "error" else None,
        metadata=metadata or {},
    )


def make_mcp(
    *,
    server_name: str = "docs",
    tool_name: str | None = "search",
    method: str = "tools/call",
    latency_ms: float = 12.0,
    status: str = "ok",
    occurred_at: datetime | None = None,
    trace_id: str | None = None,
    payload_bytes: int = 128,
) -> McpEvent:
    return McpEvent(
        event_id=uuid4(),
        occurred_at=occurred_at or datetime(2026, 11, 14, 12, 0, tzinfo=UTC),
        environment="local",
        server_name=server_name,
        transport="stdio",
        method=method,
        tool_name=tool_name,
        jsonrpc_id="1",
        latency_ms=latency_ms,
        payload_bytes=payload_bytes,
        status=status,  # type: ignore[arg-type]
        error_type="jsonrpc" if status == "error" else None,
        error_code=-32603 if status == "error" else None,
        trace_id=trace_id or str(uuid4()),
    )
