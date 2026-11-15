from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import httpx
import pytest
from starlette.testclient import TestClient

from multimcp import MemoryExporter, configure
from multimcp_proxy.streamable_http import create_app, parse_listen
from multimcp_proxy.tracker import payload_bytes_of_result

UpstreamHandler = Callable[[httpx.Request], httpx.Response]


@contextmanager
def _client(handler: UpstreamHandler) -> Iterator[tuple[TestClient, MemoryExporter]]:
    memory = MemoryExporter()
    configure(exporter=memory)
    transport = httpx.MockTransport(handler)
    upstream = httpx.AsyncClient(transport=transport)
    app = create_app(
        upstream="http://upstream.test/mcp",
        server_name="docs",
        exporter=memory,
        client=upstream,
    )
    with TestClient(app) as client:
        yield client, memory


def test_parse_listen() -> None:
    assert parse_listen("127.0.0.1:8080") == ("127.0.0.1", 8080)
    with pytest.raises(ValueError):
        parse_listen("no-port")


def test_json_response_emits_mcp_event() -> None:
    request_body = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {"name": "search", "arguments": {"q": "x"}},
        "_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
    }
    result = {"hits": [1, 2]}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/mcp"
        assert json.loads(request.content) == request_body
        assert request.headers.get("x-custom") == "keep"
        return httpx.Response(
            200,
            headers={"content-type": "application/json", "x-upstream": "yes"},
            json={"jsonrpc": "2.0", "id": "1", "result": result},
        )

    with _client(handler) as (client, memory):
        response = client.post(
            "/",
            content=json.dumps(request_body),
            headers={"content-type": "application/json", "x-custom": "keep"},
        )

    assert response.status_code == 200
    assert response.headers.get("x-upstream") == "yes"
    body = response.json()
    assert body["result"] == result
    assert len(memory.events) == 1
    event = memory.events[0]
    assert event.transport == "streamable_http"
    assert event.server_name == "docs"
    assert event.method == "tools/call"
    assert event.tool_name == "search"
    assert event.status == "ok"
    assert event.payload_bytes == payload_bytes_of_result(result)


def test_sse_response_meters_final_result_only() -> None:
    request_body = {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "t"}}
    result = {"done": True}
    progress = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"p": 1}}
    final = {"jsonrpc": "2.0", "id": 9, "result": result}
    sse = (
        f"event: message\ndata: {json.dumps(progress)}\n\n"
        f"event: message\ndata: {json.dumps(final)}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["id"] == 9
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse.encode("utf-8"),
        )

    with _client(handler) as (client, memory):
        response = client.post("/", content=json.dumps(request_body))

    assert response.status_code == 200
    assert "notifications/progress" in response.text
    assert json.dumps(final) in response.text
    assert len(memory.events) == 1
    event = memory.events[0]
    assert event.status == "ok"
    assert event.tool_name == "t"
    assert event.payload_bytes == payload_bytes_of_result(result)
    assert event.jsonrpc_id == "9"


def test_non_200_upstream_is_transport_error() -> None:
    request_body = {"jsonrpc": "2.0", "id": "x", "method": "ping"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"nope")

    with _client(handler) as (client, memory):
        response = client.post("/", content=json.dumps(request_body))

    assert response.status_code == 503
    assert response.content == b"nope"
    assert len(memory.events) == 1
    assert memory.events[0].error_type == "transport"
    assert memory.events[0].status == "error"


def test_sse_cut_before_result_is_transport() -> None:
    request_body = {
        "jsonrpc": "2.0",
        "id": "cut",
        "method": "tools/call",
        "params": {"name": "t"},
    }
    progress = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"p": 1}}
    sse = f"data: {json.dumps(progress)}\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse.encode("utf-8"),
        )

    with _client(handler) as (client, memory):
        response = client.post("/", content=json.dumps(request_body))

    assert response.status_code == 200
    assert len(memory.events) == 1
    assert memory.events[0].error_type == "transport"


def test_notification_has_no_metric_row() -> None:
    notification = {"jsonrpc": "2.0", "method": "notifications/cancelled"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202)

    with _client(handler) as (client, memory):
        response = client.post("/", content=json.dumps(notification))

    assert response.status_code == 202
    assert memory.events == []


def test_cli_http_parser() -> None:
    from multimcp_proxy.cli import build_parser

    args = build_parser().parse_args(
        [
            "http",
            "--server-name",
            "docs",
            "--listen",
            "127.0.0.1:8080",
            "--upstream",
            "http://127.0.0.1:3000/mcp",
        ]
    )
    assert args.command == "http"
    assert args.server_name == "docs"
    assert args.listen == "127.0.0.1:8080"
    assert args.upstream == "http://127.0.0.1:3000/mcp"
