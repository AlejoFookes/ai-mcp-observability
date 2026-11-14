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

## Quickstart (Compose)

Un comando levanta Postgres, API, worker de evaluación y el dashboard. El proxy MCP **no** va en Compose: corre al lado del servidor del usuario.

```bash
cp .env.example .env   # set INGEST_TOKEN (mismo valor que MULTIMCP_INGEST_TOKEN abajo)
docker compose -f deploy/compose.yaml up --build
```

Stack arriba cuando:

1. `curl -sf "http://127.0.0.1:8000/api/v1/health?ready=true"` responde 200 (`status` ok).
2. El build del front ya corrió dentro de la imagen `web` (`npm run build`). Abrí http://127.0.0.1:5173, pegá el `INGEST_TOKEN` en el formulario del shell y explorá FinOps / Latency / Traces / Compare.

Puertos: API `8000`, dashboard `5173` (nginx; `/api` se proxea a la API), Postgres `5432`.

## Envolver un cliente OpenAI

Desde otra terminal (con el stack arriba). El SDK lee `OPENAI_API_KEY` del entorno; no hardcodees claves.

```bash
uv sync   # workspace incluye multimcp[openai] en el entorno de desarrollo
export MULTIMCP_INGEST_URL=http://127.0.0.1:8000
export MULTIMCP_INGEST_TOKEN=   # mismo valor que INGEST_TOKEN del .env
```

```python
from openai import OpenAI
from multimcp import configure, prompt_context, wrap_openai

configure()  # HttpExporter via MULTIMCP_INGEST_URL / MULTIMCP_INGEST_TOKEN

client = wrap_openai(OpenAI())
with prompt_context(prompt_version="quickstart-v1", environment="local"):
    client.responses.create(model="gpt-4.1-mini", input="ping")
```

Los eventos llegan a `POST /api/v1/events` y aparecen en el dashboard (FinOps / Latency / Traces).

## Proxy MCP stdio (fuera de Compose)

El proxy reenvía JSON-RPC sin modificar el mensaje y emite telemetría MCP hacia la misma API.

```bash
uv sync
export MULTIMCP_INGEST_URL=http://127.0.0.1:8000
export MULTIMCP_INGEST_TOKEN=   # mismo INGEST_TOKEN

# Ejemplo: envolver un servidor MCP local (reemplazá el comando tras --)
uv run multimcp-proxy stdio --server-name filesystem -- \
  python -m mcp_server_filesystem
```

Apuntá tu cliente MCP al proceso del proxy (stdio) en lugar del servidor directo. Variante HTTP: `multimcp-proxy http --server-name docs --listen 127.0.0.1:8080 --upstream http://127.0.0.1:3000/mcp`.

## Desarrollo local (sin Docker)

Requiere [uv](https://docs.astral.sh/uv/) y Node 22+.

```bash
uv sync
uv run ruff check .
uv run pytest

cd apps/web && npm ci && npm run build
# Dev UI con proxy a la API: npm run dev  → http://127.0.0.1:5173
```

Detalle de imágenes y variables: [`deploy/README.md`](deploy/README.md).
