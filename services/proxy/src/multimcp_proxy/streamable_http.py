"""MCP Streamable HTTP proxy (spec revision 2026-07-28): one POST, JSON or SSE."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route

from multimcp.exporters.base import Exporter
from multimcp_proxy.sse import iter_sse_data_payloads
from multimcp_proxy.tracker import RequestTracker

logger = logging.getLogger("multimcp_proxy.http")

_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "host",
    }
)


def _filter_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


def create_app(
    *,
    upstream: str,
    server_name: str,
    exporter: Exporter | None = None,
    client: httpx.AsyncClient | None = None,
) -> Starlette:
    """Build the ASGI app that forwards each POST to `upstream` unchanged."""
    owns_client = client is None
    state: dict[str, httpx.AsyncClient] = {}

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        state["http"] = client or httpx.AsyncClient(timeout=None)
        try:
            yield
        finally:
            if owns_client:
                await state["http"].aclose()

    async def proxy(request: Request) -> Response:
        http = state["http"]
        body = await request.body()
        tracker = RequestTracker(
            server_name=server_name,
            transport="streamable_http",
            exporter=exporter,
        )
        if body:
            tracker.observe_client_message(body.decode("utf-8", errors="replace"))

        outbound = _filter_headers({k: v for k, v in request.headers.items()})
        try:
            upstream_request = http.build_request(
                "POST",
                upstream,
                headers=outbound,
                content=body,
            )
            upstream_response = await http.send(upstream_request, stream=True)
        except httpx.HTTPError:
            logger.exception("upstream request failed")
            tracker.close_open_as_transport()
            return Response(status_code=502, content=b"upstream unavailable")

        filtered = _filter_headers(upstream_response.headers)
        status = upstream_response.status_code
        content_type = upstream_response.headers.get("content-type", "")

        if status != 200:
            raw = await upstream_response.aread()
            await upstream_response.aclose()
            tracker.close_open_as_transport()
            return Response(content=raw, status_code=status, headers=filtered)

        if "text/event-stream" in content_type:

            async def event_stream() -> AsyncIterator[bytes]:
                carry = [""]
                try:
                    async for chunk in upstream_response.aiter_bytes():
                        yield chunk
                        text = chunk.decode("utf-8", errors="replace")
                        for payload in iter_sse_data_payloads(text, carry):
                            tracker.observe_server_message(payload)
                except httpx.HTTPError:
                    logger.exception("upstream SSE stream failed")
                finally:
                    await upstream_response.aclose()
                    tracker.close_open_as_transport()

            return StreamingResponse(
                event_stream(),
                status_code=status,
                headers=filtered,
                media_type=content_type,
            )

        raw = await upstream_response.aread()
        await upstream_response.aclose()
        if raw:
            tracker.observe_server_message(raw.decode("utf-8", errors="replace"))
        tracker.close_open_as_transport()
        return Response(content=raw, status_code=status, headers=filtered)

    return Starlette(
        routes=[
            Route("/", proxy, methods=["POST"]),
            Route("/{path:path}", proxy, methods=["POST"]),
        ],
        lifespan=lifespan,
    )


def run_http_proxy(
    *,
    server_name: str,
    listen: str,
    upstream: str,
    exporter: Exporter | None = None,
) -> int:
    """Serve the Streamable HTTP proxy until interrupted. Returns 0 on clean stop."""
    host, port = _parse_listen(listen)
    app = create_app(upstream=upstream, server_name=server_name, exporter=exporter)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def _parse_listen(listen: str) -> tuple[str, int]:
    if ":" not in listen:
        raise ValueError(f"listen must be HOST:PORT, got {listen!r}")
    host, _, port_s = listen.rpartition(":")
    if not host:
        host = "127.0.0.1"
    try:
        port = int(port_s)
    except ValueError as exc:
        raise ValueError(f"listen port must be an integer, got {port_s!r}") from exc
    return host, port


def parse_listen(listen: str) -> tuple[str, int]:
    """Public wrapper used by the CLI and tests."""
    return _parse_listen(listen)


def build_forward_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    """Expose header filtering for unit tests."""
    return _filter_headers({str(k): str(v) for k, v in headers.items()})
