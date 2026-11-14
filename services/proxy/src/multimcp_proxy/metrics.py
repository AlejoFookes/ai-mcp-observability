"""Emit MCP proxy events through the multimcp exporter."""

from __future__ import annotations

from multimcp import McpEvent
from multimcp.config import emit
from multimcp.context import current_context
from multimcp.exporters.base import Exporter
from multimcp.models import Transport


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
