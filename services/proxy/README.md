# multimcp-proxy

Proxy transparente para servidores MCP (revisión 2026-07-28). Reenvía JSON-RPC sin modificar el mensaje y emite telemetría vía `multimcp`.

```bash
multimcp-proxy stdio --server-name filesystem -- python -m mcp_server_filesystem
multimcp-proxy http --server-name docs --listen 127.0.0.1:8080 --upstream http://127.0.0.1:3000/mcp
```

El contrato del evento MCP está en [`SPEC.md`](../../SPEC.md), sección 5.
