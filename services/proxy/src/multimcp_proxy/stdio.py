"""MCP stdio proxy: launch a server subprocess and forward newline-delimited JSON-RPC."""

from __future__ import annotations

import contextlib
import logging
import sys
import threading
from collections.abc import Sequence
from typing import BinaryIO, TextIO

from multimcp.exporters.base import Exporter
from multimcp_proxy.framing import encode_line, iter_frames
from multimcp_proxy.metrics import emit_framing_error

logger = logging.getLogger("multimcp_proxy.stdio")


def run_stdio_proxy(
    command: Sequence[str],
    *,
    server_name: str,
    exporter: Exporter | None = None,
    client_stdin: BinaryIO | None = None,
    client_stdout: BinaryIO | None = None,
    client_stderr: TextIO | None = None,
) -> int:
    """Spawn `command`, bridge stdio, return the child exit code.

    Valid JSON lines are forwarded unchanged. Non-JSON lines are dropped, emit a
    framing error event, and never appear on the other end. Child stderr is copied
    to the proxy stderr and never becomes a tool/framing failure.
    """
    import subprocess

    if not command:
        raise ValueError("stdio proxy requires a non-empty server command")

    stdin_src = client_stdin if client_stdin is not None else sys.stdin.buffer
    stdout_dst = client_stdout if client_stdout is not None else sys.stdout.buffer
    stderr_dst = client_stderr if client_stderr is not None else sys.stderr

    child = subprocess.Popen(
        list(command),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    assert child.stdin is not None
    assert child.stdout is not None
    assert child.stderr is not None

    errors: list[BaseException] = []

    def pump_client_to_server() -> None:
        try:
            for frame in iter_frames(stdin_src):
                if not frame.ok:
                    emit_framing_error(
                        server_name=server_name,
                        transport="stdio",
                        payload_bytes=len(frame.raw),
                        exporter=exporter,
                    )
                    continue
                child.stdin.write(encode_line(frame.text))
                child.stdin.flush()
        except BaseException as exc:
            errors.append(exc)
            logger.exception("client→server pump failed")
        finally:
            with contextlib.suppress(OSError):
                child.stdin.close()

    def pump_server_to_client() -> None:
        try:
            for frame in iter_frames(child.stdout):
                if not frame.ok:
                    emit_framing_error(
                        server_name=server_name,
                        transport="stdio",
                        payload_bytes=len(frame.raw),
                        exporter=exporter,
                    )
                    continue
                stdout_dst.write(encode_line(frame.text))
                stdout_dst.flush()
        except BaseException as exc:
            errors.append(exc)
            logger.exception("server→client pump failed")

    def pump_stderr() -> None:
        try:
            assert child.stderr is not None
            while True:
                chunk = child.stderr.read(4096)
                if not chunk:
                    return
                text = chunk.decode("utf-8", errors="replace")
                stderr_dst.write(text)
                stderr_dst.flush()
        except BaseException as exc:
            errors.append(exc)
            logger.exception("stderr pump failed")

    threads = [
        threading.Thread(target=pump_client_to_server, name="mcp-stdin", daemon=True),
        threading.Thread(target=pump_server_to_client, name="mcp-stdout", daemon=True),
        threading.Thread(target=pump_stderr, name="mcp-stderr", daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    return_code = child.wait()
    if errors:
        logger.error("stdio proxy finished with %s pump error(s)", len(errors))
    return return_code if return_code is not None else 1
