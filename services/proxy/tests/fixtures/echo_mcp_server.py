"""Minimal newline-delimited JSON-RPC server for proxy tests. No network."""

from __future__ import annotations

import json
import sys


def main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write("not-json-from-server\n")
            sys.stdout.flush()
            continue

        method = message.get("method")
        sys.stderr.write(f"seen:{method}\n")
        sys.stderr.flush()

        if method == "emit_garbage":
            sys.stdout.write("<<<not-json>>>\n")
            sys.stdout.flush()
            continue

        response = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "echo_method": method,
                "echo_params": message.get("params"),
                "echo_meta": message.get("_meta"),
            },
        }
        # Compact JSON so the test can assert the exact forwarded bytes.
        sys.stdout.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False))
        sys.stdout.write("\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
