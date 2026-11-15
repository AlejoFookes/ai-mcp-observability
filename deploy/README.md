# Deploy

Stack Compose: Postgres 16, API, eval worker y dashboard web (SPEC §10). Sin Redis. El proxy MCP no entra en Compose.

```bash
cp .env.example .env   # set INGEST_TOKEN
docker compose -f deploy/compose.yaml up --build
```

| Servicio | URL / comando |
| --- | --- |
| API | http://127.0.0.1:8000 — listo cuando `GET /api/v1/health?ready=true` es 200 |
| Dashboard | http://127.0.0.1:5173 — nginx sirve el build de `apps/web` y proxea `/api` a la API |
| Worker | misma imagen que la API, `python -m multimcp_api.eval.worker` |
| Proxy | fuera de Compose: `multimcp-proxy stdio ...` al lado del servidor MCP |

Imágenes:

- `deploy/Dockerfile.api` — `uv sync --package multimcp-api`, migraciones en el entrypoint.
- `deploy/Dockerfile.web` — `npm ci && npm run build`, luego nginx + `deploy/nginx.web.conf`.
