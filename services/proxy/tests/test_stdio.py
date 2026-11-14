from __future__ import annotations

import json
import sys
from io import BytesIO, StringIO
from pathlib import Path

from multimcp import MemoryExporter, configure
from multimcp_proxy.stdio import run_stdio_proxy

FIXTURE = Path(__file__).parent / "fixtures" / "echo_mcp_server.py"


def _run(
    request_line: str,
    *,
    exporter: MemoryExporter | None = None,
) -> tuple[int, bytes, str, MemoryExporter]:
    memory = exporter or MemoryExporter()
    configure(exporter=memory)
    stdout = BytesIO()
    stderr = StringIO()
    code = run_stdio_proxy(
        [sys.executable, str(FIXTURE)],
        server_name="echo",
        exporter=memory,
        client_stdin=BytesIO((request_line + "\n").encode("utf-8")),
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
    assert memory.events == []

    response = json.loads(stdout.decode("utf-8").strip())
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "42"
    assert response["result"]["echo_method"] == "tools/call"
    assert response["result"]["echo_params"] == request["params"]
    assert response["result"]["echo_meta"] == request["_meta"]


def test_stderr_is_forwarded_and_does_not_create_events() -> None:
    request = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    code, _stdout, stderr, memory = _run(json.dumps(request))

    assert code == 0
    assert "seen:ping" in stderr
    assert memory.events == []


def test_invalid_server_stdout_emits_framing_and_is_not_forwarded() -> None:
    request = {"jsonrpc": "2.0", "id": 7, "method": "emit_garbage"}
    code, stdout, _stderr, memory = _run(json.dumps(request))

    assert code == 0
    assert stdout == b""
    assert len(memory.events) == 1
    event = memory.events[0]
    assert event.status == "error"
    assert event.error_type == "framing"
    assert event.server_name == "echo"
    assert event.transport == "stdio"
    assert event.method == "unknown"
    assert event.payload_bytes > 0


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
