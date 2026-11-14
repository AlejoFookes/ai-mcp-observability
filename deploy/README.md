# Deploy

```bash
cp .env.example .env   # set INGEST_TOKEN
docker compose -f deploy/compose.yaml up --build
```

- API: http://127.0.0.1:8000 — `GET /api/v1/health?ready=true` is 200 when Postgres accepts connections.
- Worker: same image as API, command `python -m multimcp_api.eval.worker`.
- No Redis. Proxy MCP stays outside Compose.
