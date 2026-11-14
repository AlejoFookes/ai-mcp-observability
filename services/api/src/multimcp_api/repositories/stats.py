"""Shared aggregation helpers for Memory and (tests of) Postgres semantics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from multimcp.models import GenAIEvent, McpEvent
from multimcp_api.domain.models import (
    CompareQuery,
    CompareResult,
    CompareSide,
    FinOpsRow,
    LatencyRow,
    TraceSpan,
    WindowQuery,
)


def percentile_cont(values: Sequence[float], p: float) -> float:
    """PostgreSQL-compatible percentile_cont over a sorted sample."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * p
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[low])
    weight = rank - low
    return float(ordered[low]) * (1.0 - weight) + float(ordered[high]) * weight


def in_window(occurred_at: datetime, start: datetime, end: datetime) -> bool:
    return start <= occurred_at < end


def is_judge(event: GenAIEvent) -> bool:
    role = event.metadata.get("role")
    return role == "judge"


def genai_group_key(event: GenAIEvent, group_by: str) -> str:
    if group_by == "model":
        return f"{event.provider}/{event.model}"
    if group_by == "provider":
        return event.provider
    if group_by == "prompt_version":
        return event.prompt_version or ""
    if group_by == "operation":
        return event.operation
    raise ValueError(f"unsupported genai group_by: {group_by}")


def mcp_group_key(event: McpEvent, group_by: str) -> str:
    if group_by == "mcp_server":
        return event.server_name
    if group_by == "mcp_tool":
        if event.tool_name:
            return f"{event.server_name}/{event.tool_name}"
        return event.server_name
    raise ValueError(f"unsupported mcp group_by: {group_by}")


def aggregate_finops_genai(
    events: Sequence[GenAIEvent], query: WindowQuery
) -> list[FinOpsRow]:
    buckets: dict[str, dict[str, Any]] = {}
    for event in events:
        if not in_window(event.occurred_at, query.start, query.end):
            continue
        if not query.include_judge and is_judge(event):
            continue
        key = genai_group_key(event, query.group_by)
        bucket = buckets.setdefault(
            key,
            {
                "request_count": 0,
                "error_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "estimated_cost_usd": Decimal("0"),
                "unpriced_count": 0,
            },
        )
        bucket["request_count"] += 1
        if event.status == "error":
            bucket["error_count"] += 1
        bucket["input_tokens"] += event.input_tokens or 0
        bucket["output_tokens"] += event.output_tokens or 0
        if event.price_status == "priced" and event.estimated_cost_usd is not None:
            bucket["estimated_cost_usd"] += event.estimated_cost_usd
        else:
            bucket["unpriced_count"] += 1
    return [
        FinOpsRow(key=key, **values)  # type: ignore[arg-type]
        for key, values in sorted(buckets.items())
    ]


def aggregate_finops_mcp(events: Sequence[McpEvent], query: WindowQuery) -> list[FinOpsRow]:
    buckets: dict[str, int] = {}
    errors: dict[str, int] = {}
    for event in events:
        if not in_window(event.occurred_at, query.start, query.end):
            continue
        key = mcp_group_key(event, "mcp_server")
        buckets[key] = buckets.get(key, 0) + 1
        if event.status == "error":
            errors[key] = errors.get(key, 0) + 1
    return [
        FinOpsRow(
            key=key,
            request_count=count,
            error_count=errors.get(key, 0),
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=Decimal("0"),
            unpriced_count=0,
        )
        for key, count in sorted(buckets.items())
    ]


def aggregate_latency_genai(
    events: Sequence[GenAIEvent], query: WindowQuery
) -> list[LatencyRow]:
    buckets: dict[str, list[GenAIEvent]] = {}
    for event in events:
        if not in_window(event.occurred_at, query.start, query.end):
            continue
        key = genai_group_key(event, query.group_by)
        buckets.setdefault(key, []).append(event)
    rows: list[LatencyRow] = []
    for key, group in sorted(buckets.items()):
        latencies = [float(e.latency_ms) for e in group]
        error_count = sum(1 for e in group if e.status == "error")
        rows.append(
            LatencyRow(
                key=key,
                count=len(group),
                p50_ms=percentile_cont(latencies, 0.50),
                p95_ms=percentile_cont(latencies, 0.95),
                error_rate=error_count / len(group),
            )
        )
    return rows


def aggregate_latency_mcp(events: Sequence[McpEvent], query: WindowQuery) -> list[LatencyRow]:
    buckets: dict[str, list[McpEvent]] = {}
    for event in events:
        if not in_window(event.occurred_at, query.start, query.end):
            continue
        key = mcp_group_key(event, "mcp_tool")
        buckets.setdefault(key, []).append(event)
    rows: list[LatencyRow] = []
    for key, group in sorted(buckets.items()):
        latencies = [float(e.latency_ms) for e in group]
        error_count = sum(1 for e in group if e.status == "error")
        rows.append(
            LatencyRow(
                key=key,
                count=len(group),
                p50_ms=percentile_cont(latencies, 0.50),
                p95_ms=percentile_cont(latencies, 0.95),
                error_rate=error_count / len(group),
            )
        )
    return rows


def build_trace(
    genai: Sequence[GenAIEvent], mcp: Sequence[McpEvent], trace_id: str
) -> list[TraceSpan]:
    spans: list[TraceSpan] = []
    for event in genai:
        if event.trace_id != trace_id:
            continue
        spans.append(
            TraceSpan(
                kind="genai",
                event_id=event.event_id,
                occurred_at=event.occurred_at,
                trace_id=event.trace_id,
                status=event.status,
                latency_ms=float(event.latency_ms),
                label=f"{event.provider}/{event.model}",
                detail={
                    "operation": event.operation,
                    "prompt_version": event.prompt_version,
                },
            )
        )
    for event in mcp:
        if event.trace_id != trace_id:
            continue
        spans.append(
            TraceSpan(
                kind="mcp",
                event_id=event.event_id,
                occurred_at=event.occurred_at,
                trace_id=event.trace_id,
                status=event.status,
                latency_ms=float(event.latency_ms),
                label=event.tool_name or event.method,
                detail={
                    "server_name": event.server_name,
                    "method": event.method,
                    "tool_name": event.tool_name,
                },
            )
        )
    spans.sort(key=lambda span: span.occurred_at)
    return spans


def compare_side(
    events: Sequence[GenAIEvent], query: CompareQuery, key: str
) -> CompareSide:
    matched: list[GenAIEvent] = []
    for event in events:
        if not in_window(event.occurred_at, query.start, query.end):
            continue
        if query.dimension == "prompt_version":
            if (event.prompt_version or "") != key:
                continue
        else:
            if f"{event.provider}/{event.model}" != key:
                continue
        matched.append(event)
    if not matched:
        return CompareSide(
            key=key,
            request_count=0,
            error_count=0,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=Decimal("0"),
            unpriced_count=0,
            p50_ms=None,
            p95_ms=None,
            error_rate=0.0,
        )
    latencies = [float(e.latency_ms) for e in matched]
    error_count = sum(1 for e in matched if e.status == "error")
    cost = Decimal("0")
    unpriced = 0
    for event in matched:
        if event.price_status == "priced" and event.estimated_cost_usd is not None:
            cost += event.estimated_cost_usd
        else:
            unpriced += 1
    return CompareSide(
        key=key,
        request_count=len(matched),
        error_count=error_count,
        input_tokens=sum(e.input_tokens or 0 for e in matched),
        output_tokens=sum(e.output_tokens or 0 for e in matched),
        estimated_cost_usd=cost,
        unpriced_count=unpriced,
        p50_ms=percentile_cont(latencies, 0.50),
        p95_ms=percentile_cont(latencies, 0.95),
        error_rate=error_count / len(matched),
    )


def build_compare(events: Sequence[GenAIEvent], query: CompareQuery) -> CompareResult:
    return CompareResult(
        left=compare_side(events, query, query.left),
        right=compare_side(events, query, query.right),
    )


def as_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
