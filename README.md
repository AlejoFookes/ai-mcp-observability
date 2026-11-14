# multiMCP

Plataforma portable de observabilidad, FinOps y evaluación para pipelines de IA generativa, SDKs y servidores [MCP](https://modelcontextprotocol.io/specification/2026-07-28).

Este repositorio está en la fase de especificación. El código de la plataforma arranca después de aprobar [`SPEC.md`](SPEC.md). El orden de construcción está en [`ROADMAP.md`](ROADMAP.md).

| Paquete | Ruta | Rol |
| --- | --- | --- |
| `multimcp` `0.1.0` | `sdks/python` | Wrappers de `openai`, `anthropic` y `google-genai`, más el catálogo de precios |
| `multimcp-proxy` | `services/proxy` | Interceptor MCP `stdio` y Streamable HTTP |
| `multimcp-api` | `services/api` | Ingesta, consultas y evaluador RAG |
| `@multimcp/web` | `apps/web` | Dashboard FinOps, latencia, trazas y comparación |

Licencia: [MIT](LICENSE).

## Desarrollo

Requiere [uv](https://docs.astral.sh/uv/). Desde la raíz:

```bash
uv sync
uv run ruff check .
uv run pytest
```
