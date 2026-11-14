# multimcp-proxy

Proxy transparente para servidores MCP (revisión 2026-07-28). Reenvía JSON-RPC sin modificar el mensaje y emite telemetría vía `multimcp`.

```bash
multimcp-proxy stdio --server-name filesystem -- python -m mcp_server_filesystem
```

El contrato del evento MCP está en [`SPEC.md`](../../SPEC.md), sección 5.
