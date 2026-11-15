"""Emit MCP proxy events through the multimcp exporter."""

from __future__ import annotations

from multimcp import McpEvent
from multimcp.config import emit
from multimcp.context import current_context
from multimcp.exporters.base import Exporter
from multimcp.models import McpErrorType, Status, Transport


def emit_framing_error(
    *,
    server_name: str,
    transport: Transport,
    payload_bytes: int,
    exporter: Exporter | None = None,
) -> None:
    """Record a line that was not valid JSON. Does not raise on exporter failure."""
    ctx = current_context()
    event = McpEvent(
        environment=ctx.environment,
        server_name=server_name,
        transport=transport,
        method="unknown",
        tool_name=None,
        jsonrpc_id=None,
        latency_ms=0.0,
        payload_bytes=payload_bytes,
        status="error",
        error_code=None,
        error_type="framing",
        trace_id=ctx.trace_id,
    )
    emit(event, exporter=exporter)


def emit_mcp_event(
    *,
    server_name: str,
    transport: Transport,
    method: str,
    tool_name: str | None,
    jsonrpc_id: str | None,
    latency_ms: float,
    payload_bytes: int,
    status: Status,
    error_type: McpErrorType | None = None,
    error_code: int | None = None,
    exporter: Exporter | None = None,
    trace_id: str | None = None,
) -> None:
    """Emit one completed (or failed) JSON-RPC request seen by the proxy."""
    ctx = current_context()
    event = McpEvent(
        environment=ctx.environment,
        server_name=server_name,
        transport=transport,
        method=method,
        tool_name=tool_name,
        jsonrpc_id=jsonrpc_id,
        latency_ms=latency_ms,
        payload_bytes=payload_bytes,
        status=status,
        error_code=error_code,
        error_type=error_type,
        trace_id=trace_id or ctx.trace_id,
    )
    emit(event, exporter=exporter)
