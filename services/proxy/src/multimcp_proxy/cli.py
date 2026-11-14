"""CLI entry point: `multimcp-proxy`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from multimcp_proxy.stdio import run_stdio_proxy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="multimcp-proxy",
        description="Transparent MCP proxy with multiMCP telemetry (spec 2026-07-28).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    stdio = sub.add_parser(
        "stdio",
        help="Launch an MCP server as a subprocess and bridge newline-delimited JSON-RPC.",
    )
    stdio.add_argument(
        "--server-name",
        required=True,
        help="Logical server name written on every McpEvent.",
    )
    stdio.add_argument(
        "server_command",
        nargs=argparse.REMAINDER,
        help="Server argv after `--`, e.g. `-- python -m my_mcp_server`.",
    )
    return parser


def _normalize_server_command(raw: Sequence[str]) -> list[str]:
    parts = list(raw)
    if parts and parts[0] == "--":
        parts = parts[1:]
    return parts


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "stdio":
        server_command = _normalize_server_command(args.server_command)
        if not server_command:
            parser.error("stdio requires a server command after `--`")
        return run_stdio_proxy(server_command, server_name=args.server_name)

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
