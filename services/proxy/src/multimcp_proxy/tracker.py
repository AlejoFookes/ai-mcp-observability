"""Match JSON-RPC requests to responses and build McpEvent fields."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any

from multimcp.context import current_context
from multimcp.exporters.base import Exporter
from multimcp.models import McpErrorType, Transport
from multimcp_proxy.metrics import emit_mcp_event


def _jsonrpc_id_key(value: Any) -> str | None:
    """Normalize a JSON-RPC id for the pending map. None / missing → notification."""
    if value is None:
        return None
    if isinstance(value, bool):
        # JSON-RPC ids are string | number | null; bool is not valid but avoid True→"1".
        return None
    if isinstance(value, (str, int, float)):
        return str(value)
    return None


def tool_name_from_params(method: str, params: Any) -> str | None:
    if method != "tools/call":
        return None
    if isinstance(params, dict):
        name = params.get("name")
        if isinstance(name, str) and name:
            return name
    return None


def payload_bytes_of_result(result: Any) -> int:
    return len(json.dumps(result).encode("utf-8"))


@dataclass(slots=True)
class PendingRequest:
    method: str
    tool_name: str | None
    jsonrpc_id: str
    started: float
    trace_id: str


class RequestTracker:
    """Thread-safe pending-request table for one proxy session."""

    def __init__(
        self,
        *,
        server_name: str,
        transport: Transport = "stdio",
        exporter: Exporter | None = None,
    ) -> None:
        self._server_name = server_name
        self._transport = transport
        self._exporter = exporter
        self._lock = threading.Lock()
        self._pending: dict[str, PendingRequest] = {}

    def observe_client_message(self, text: str) -> None:
        """Register a request with an id. Notifications are ignored for metrics."""
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            return
        if not isinstance(message, dict):
            return
        key = _jsonrpc_id_key(message.get("id"))
        if key is None:
            return
        # Responses/errors from the client are unexpected on stdio; ignore for metrics.
        if "method" not in message:
            return
        method = message.get("method")
        if not isinstance(method, str) or not method:
            method = "unknown"
        ctx = current_context()
        pending = PendingRequest(
            method=method,
            tool_name=tool_name_from_params(method, message.get("params")),
            jsonrpc_id=key,
            started=time.perf_counter(),
            trace_id=ctx.trace_id,
        )
        with self._lock:
            self._pending[key] = pending

    def observe_server_message(self, text: str) -> None:
        """Complete a pending request when a response/error with matching id arrives."""
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            return
        if not isinstance(message, dict):
            return
        key = _jsonrpc_id_key(message.get("id"))
        if key is None:
            return
        # Server notifications / requests toward the client are not in-flight client calls.
        if "method" in message and "result" not in message and "error" not in message:
            return

        with self._lock:
            pending = self._pending.pop(key, None)
        if pending is None:
            return

        latency_ms = (time.perf_counter() - pending.started) * 1000.0
        if "error" in message:
            error = message.get("error")
            error_code = error.get("code") if isinstance(error, dict) else None
            if not isinstance(error_code, int):
                error_code = None
            self._emit(
                pending,
                latency_ms=latency_ms,
                payload_bytes=0,
                status="error",
                error_type="jsonrpc",
                error_code=error_code,
            )
            return

        result = message.get("result")
        self._emit(
            pending,
            latency_ms=latency_ms,
            payload_bytes=payload_bytes_of_result(result),
            status="ok",
            error_type=None,
            error_code=None,
        )

    def close_open_as_transport(self) -> None:
        """Mark every unanswered request as a transport failure (child died / EOF)."""
        with self._lock:
            leftover = list(self._pending.values())
            self._pending.clear()
        now = time.perf_counter()
        for pending in leftover:
            self._emit(
                pending,
                latency_ms=(now - pending.started) * 1000.0,
                payload_bytes=0,
                status="error",
                error_type="transport",
                error_code=None,
            )

    def _emit(
        self,
        pending: PendingRequest,
        *,
        latency_ms: float,
        payload_bytes: int,
        status: str,
        error_type: McpErrorType | None,
        error_code: int | None,
    ) -> None:
        emit_mcp_event(
            server_name=self._server_name,
            transport=self._transport,
            method=pending.method,
            tool_name=pending.tool_name,
            jsonrpc_id=pending.jsonrpc_id,
            latency_ms=latency_ms,
            payload_bytes=payload_bytes,
            status=status,
            error_type=error_type,
            error_code=error_code,
            exporter=self._exporter,
            trace_id=pending.trace_id,
        )
