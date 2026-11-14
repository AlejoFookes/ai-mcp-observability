"""Newline-delimited JSON-RPC framing for MCP stdio (2026-07-28)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO, Literal


@dataclass(frozen=True, slots=True)
class Frame:
    """One newline-terminated payload read from a stream."""

    raw: bytes
    text: str
    ok: bool


def decode_line(raw: bytes) -> Frame:
    """Parse one line (without the trailing newline). Empty or non-JSON → not ok."""
    text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        return Frame(raw=raw, text=text, ok=False)
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return Frame(raw=raw, text=text, ok=False)
    return Frame(raw=raw, text=text, ok=True)


def encode_line(text: str) -> bytes:
    """Serialize a JSON text line with a trailing newline, unchanged payload."""
    return text.encode("utf-8") + b"\n"


def iter_frames(stream: BinaryIO) -> Iterator[Frame]:
    """Yield frames as complete lines arrive. Stops on EOF."""
    buffer = bytearray()
    while True:
        chunk = stream.read(4096)
        if not chunk:
            if buffer:
                yield decode_line(bytes(buffer))
            return
        buffer.extend(chunk)
        while True:
            newline_at = buffer.find(b"\n")
            if newline_at < 0:
                break
            line = bytes(buffer[:newline_at])
            del buffer[: newline_at + 1]
            # Strip a trailing CR from CRLF without altering JSON content otherwise.
            if line.endswith(b"\r"):
                line = line[:-1]
            yield decode_line(line)


Direction = Literal["client_to_server", "server_to_client"]
