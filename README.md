# multiMCP

Plataforma portable de observabilidad, FinOps y evaluación para pipelines de IA generativa, SDKs y servidores [MCP](https://modelcontextprotocol.io/specification/2026-07-28).

Fuente de verdad: [`SPEC.md`](SPEC.md). Orden de construcción: [`ROADMAP.md`](ROADMAP.md).

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

## Compose (API + worker + Postgres)

```bash
cp .env.example .env   # set INGEST_TOKEN
docker compose -f deploy/compose.yaml up --build
```

Health: `GET http://127.0.0.1:8000/api/v1/health?ready=true` → 200 cuando Postgres acepta conexiones. El proxy MCP no va en Compose; corre al lado del servidor del usuario (`multimcp-proxy stdio ...`).
