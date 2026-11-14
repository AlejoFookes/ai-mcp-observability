"""Minimal SSE frame parser for Streamable HTTP response bodies."""

from __future__ import annotations

from collections.abc import Iterator


def iter_sse_data_payloads(chunk_text: str, buffer: list[str]) -> Iterator[str]:
    """Feed decoded SSE text; yield complete `data:` payloads (joined multi-line data).

    `buffer` is a one-element list holding the carry-over string between chunks.
    """
    buffer[0] += chunk_text
    while True:
        sep = buffer[0].find("\n\n")
        if sep < 0:
            # Support CRLF event terminators.
            sep = buffer[0].find("\r\n\r\n")
            if sep < 0:
                return
            event_block = buffer[0][:sep]
            buffer[0] = buffer[0][sep + 4 :]
        else:
            event_block = buffer[0][:sep]
            buffer[0] = buffer[0][sep + 2 :]

        data_lines: list[str] = []
        for raw_line in event_block.splitlines():
            line = raw_line[:-1] if raw_line.endswith("\r") else raw_line
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if data_lines:
            yield "\n".join(data_lines)
