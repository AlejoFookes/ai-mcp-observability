from __future__ import annotations

import json
import sys
from io import BytesIO, StringIO
from pathlib import Path

from multimcp import MemoryExporter, configure
from multimcp_proxy.stdio import run_stdio_proxy
from multimcp_proxy.tracker import payload_bytes_of_result

FIXTURE = Path(__file__).parent / "fixtures" / "echo_mcp_server.py"


def _run(
    lines: str | list[str],
    *,
    exporter: MemoryExporter | None = None,
) -> tuple[int, bytes, str, MemoryExporter]:
    memory = exporter or MemoryExporter()
    configure(exporter=memory)
    if isinstance(lines, str):
        payload = (lines + "\n").encode("utf-8")
    else:
        payload = "".join(line + "\n" for line in lines).encode("utf-8")
    stdout = BytesIO()
    stderr = StringIO()
    code = run_stdio_proxy(
        [sys.executable, str(FIXTURE)],
        server_name="echo",
        exporter=memory,
        client_stdin=BytesIO(payload),
        client_stdout=stdout,
        client_stderr=stderr,
    )
    return code, stdout.getvalue(), stderr.getvalue(), memory


def test_forwards_jsonrpc_without_changing_fields() -> None:
    request = {
        "jsonrpc": "2.0",
        "id": "42",
        "method": "tools/call",
        "params": {"name": "read_file", "arguments": {"path": "/tmp/a"}},
        "_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
    }
    line = json.dumps(request, separators=(",", ":"), ensure_ascii=False)
    code, stdout, stderr, memory = _run(line)

    assert code == 0
    assert "seen:tools/call" in stderr

    response = json.loads(stdout.decode("utf-8").strip())
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "42"
    assert response["result"]["echo_method"] == "tools/call"
    assert response["result"]["echo_params"] == request["params"]
    assert response["result"]["echo_meta"] == request["_meta"]

    assert len(memory.events) == 1
    event = memory.events[0]
    assert event.method == "tools/call"
    assert event.tool_name == "read_file"
    assert event.jsonrpc_id == "42"
    assert event.status == "ok"
    assert event.error_type is None
    assert event.payload_bytes == payload_bytes_of_result(response["result"])
    assert event.latency_ms >= 0


def test_stderr_is_forwarded_and_does_not_create_framing_events() -> None:
    request = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    code, _stdout, stderr, memory = _run(json.dumps(request))

    assert code == 0
    assert "seen:ping" in stderr
    assert len(memory.events) == 1
    assert memory.events[0].method == "ping"
    assert memory.events[0].tool_name is None
    assert memory.events[0].error_type is None


def test_notification_is_forwarded_without_event() -> None:
    notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    code, stdout, _stderr, memory = _run(json.dumps(notification))

    assert code == 0
    # Fixture echoes notifications that carry no id as a response with id=null;
    # the important bit is the proxy did not record a metric row for them.
    assert len(memory.events) == 0
    assert stdout  # still forwarded to the server and may produce a reply line


def test_invalid_server_stdout_emits_framing_and_is_not_forwarded() -> None:
    request = {"jsonrpc": "2.0", "id": 7, "method": "emit_garbage"}
    code, stdout, _stderr, memory = _run(json.dumps(request))

    assert code == 0
    assert stdout == b""
    framing = [e for e in memory.events if e.error_type == "framing"]
    transport = [e for e in memory.events if e.error_type == "transport"]
    assert len(framing) == 1
    assert framing[0].method == "unknown"
    assert framing[0].server_name == "echo"
    # Pending request never got a JSON-RPC response → closed as transport on exit.
    assert len(transport) == 1
    assert transport[0].method == "emit_garbage"
    assert transport[0].jsonrpc_id == "7"


def test_invalid_client_line_is_dropped_with_framing_event() -> None:
    memory = MemoryExporter()
    configure(exporter=memory)
    stdout = BytesIO()
    code = run_stdio_proxy(
        [sys.executable, str(FIXTURE)],
        server_name="echo",
        exporter=memory,
        client_stdin=BytesIO(b"this-is-not-json\n"),
        client_stdout=stdout,
        client_stderr=StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == b""
    assert len(memory.events) == 1
    assert memory.events[0].error_type == "framing"


def test_jsonrpc_error_sets_error_type_and_code() -> None:
    request = {"jsonrpc": "2.0", "id": "err-1", "method": "return_error", "params": {}}
    code, stdout, _stderr, memory = _run(json.dumps(request))

    assert code == 0
    body = json.loads(stdout.decode("utf-8").strip())
    assert body["error"]["code"] == -32602
    assert len(memory.events) == 1
    event = memory.events[0]
    assert event.status == "error"
    assert event.error_type == "jsonrpc"
    assert event.error_code == -32602
    assert event.payload_bytes == 0


def test_child_exit_mid_request_emits_transport() -> None:
    request = {"jsonrpc": "2.0", "id": "die-1", "method": "die"}
    code, stdout, _stderr, memory = _run(json.dumps(request))

    assert code == 1
    assert stdout == b""
    assert len(memory.events) == 1
    event = memory.events[0]
    assert event.status == "error"
    assert event.error_type == "transport"
    assert event.error_code is None
    assert event.jsonrpc_id == "die-1"
