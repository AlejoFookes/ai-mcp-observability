import json
import logging
import threading

import httpx
import pytest

from multimcp import GenAIEvent, HttpExporter, McpEvent, MemoryExporter, configure
from multimcp.config import emit, get_exporter


def _genai(i: int = 0) -> GenAIEvent:
    return GenAIEvent(
        environment="test", trace_id=f"t{i}", provider="openai", model="gpt-5.5",
        operation="responses.create", latency_ms=1.0, price_status="unpriced", status="ok",
    )


def _mcp() -> McpEvent:
    return McpEvent(
        environment="test", trace_id="t", server_name="fs", transport="stdio",
        method="tools/call", tool_name="read_file", latency_ms=1.0, payload_bytes=10, status="ok",
    )


class Recorder:
    def __init__(self, status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json={"schema_version": "1.0"})

    def bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests]


def _exporter(handler, **kwargs) -> HttpExporter:
    return HttpExporter(
        url="http://ingest.test", token="secret-token", background=False,
        transport=httpx.MockTransport(handler), **kwargs,
    )


def test_memory_exporter_keeps_events_and_honors_maxlen():
    exporter = MemoryExporter(maxlen=2)
    exporter.insert([_genai(1), _genai(2), _genai(3)])
    assert [e.trace_id for e in exporter.events] == ["t2", "t3"]
    exporter.clear()
    assert exporter.events == []


def test_http_posts_bearer_and_schema_version():
    recorder = Recorder()
    exporter = _exporter(recorder)
    exporter.insert([_genai()])
    exporter.flush()
    (request,) = recorder.requests
    assert request.url == "http://ingest.test/api/v1/events"
    assert request.headers["Authorization"] == "Bearer secret-token"
    (body,) = recorder.bodies()
    assert body["schema_version"] == "1.0"
    assert body["events"][0]["schema_version"] == "1.0"


def test_http_routes_mcp_events_to_their_endpoint():
    recorder = Recorder()
    exporter = _exporter(recorder)
    exporter.insert([_genai(), _mcp()])
    exporter.flush()
    assert sorted(r.url.path for r in recorder.requests) == ["/api/v1/events", "/api/v1/mcp-events"]


def test_http_batches_at_most_one_hundred():
    recorder = Recorder()
    exporter = _exporter(recorder)
    exporter.insert([_genai(i) for i in range(250)])
    exporter.flush()
    assert [len(b["events"]) for b in recorder.bodies()] == [100, 100, 50]


def test_http_buffer_drops_oldest_when_full(caplog):
    recorder = Recorder()
    exporter = _exporter(recorder, buffer_size=1000)
    with caplog.at_level(logging.WARNING, logger="multimcp"):
        exporter.insert([_genai(i) for i in range(1005)])
    exporter.flush()
    sent = [e["trace_id"] for b in recorder.bodies() for e in b["events"]]
    assert len(sent) == 1000
    assert sent[0] == "t5"
    assert "dropped 5 oldest" in caplog.text


@pytest.mark.parametrize("handler", [Recorder(status=500), Recorder(status=401)])
def test_http_error_status_is_logged_and_dropped(handler, caplog):
    exporter = _exporter(handler)
    exporter.insert([_genai()])
    with caplog.at_level(logging.WARNING, logger="multimcp"):
        exporter.flush()
    assert "dropped 1 events" in caplog.text
    exporter.flush()
    assert len(handler.requests) == 1


def test_http_network_error_is_logged_not_raised(caplog):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    exporter = _exporter(refuse)
    exporter.insert([_genai()])
    with caplog.at_level(logging.WARNING, logger="multimcp"):
        exporter.flush()
    assert "ConnectError" in caplog.text
    assert "secret-token" not in caplog.text


def test_http_uses_environment_defaults(monkeypatch):
    monkeypatch.setenv("MULTIMCP_INGEST_URL", "http://from-env.test")
    monkeypatch.setenv("MULTIMCP_INGEST_TOKEN", "env-token")
    recorder = Recorder()
    exporter = HttpExporter(background=False, transport=httpx.MockTransport(recorder))
    exporter.insert([_genai()])
    exporter.flush()
    assert recorder.requests[0].url.host == "from-env.test"
    assert recorder.requests[0].headers["Authorization"] == "Bearer env-token"


def test_http_without_token_sends_no_authorization(monkeypatch):
    monkeypatch.delenv("MULTIMCP_INGEST_TOKEN", raising=False)
    recorder = Recorder()
    exporter = HttpExporter(
        url="http://ingest.test", background=False, transport=httpx.MockTransport(recorder)
    )
    exporter.insert([_genai()])
    exporter.flush()
    assert "Authorization" not in recorder.requests[0].headers


def test_background_thread_flushes_and_close_drains():
    sent = threading.Event()
    recorder = Recorder()

    def handler(request: httpx.Request) -> httpx.Response:
        response = recorder(request)
        sent.set()
        return response

    exporter = HttpExporter(
        url="http://ingest.test", batch_size=1, transport=httpx.MockTransport(handler)
    )
    exporter.insert([_genai()])
    assert sent.wait(timeout=5)
    exporter.insert([_genai(2)])
    exporter.close()
    assert sum(len(b["events"]) for b in recorder.bodies()) == 2


def test_emit_survives_a_broken_exporter(caplog):
    class Broken:
        def insert(self, events):
            raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="multimcp"):
        emit(_genai(), exporter=Broken())
    assert "exporter failed" in caplog.text


def test_configure_sets_process_exporter(monkeypatch):
    monkeypatch.delenv("MULTIMCP_INGEST_URL", raising=False)
    memory = MemoryExporter()
    configure(exporter=memory)
    try:
        emit(_genai())
        assert len(memory.events) == 1
    finally:
        configure(exporter=None)
    assert get_exporter() is None
