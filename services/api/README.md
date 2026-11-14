# multimcp-api

API FastAPI de multiMCP: ingesta de eventos, FinOps, latencia, trazas y evaluación RAG.

```bash
uv run multimcp-api
# o: uv run uvicorn multimcp_api.main:app --reload
```

Worker de evaluación (solo con `STORAGE_BACKEND=postgres`):

```bash
uv run python -m multimcp_api.eval.worker
```

## Storage

| `STORAGE_BACKEND` | Repositorio | Evaluación |
| --- | --- | --- |
| `postgres` (default) | `PostgresEventRepository` | `EVAL_BACKEND=postgres` (worker) o `inline` |
| `bigquery` | `BigQueryEventRepository` (extra `bigquery`) | **solo** `EVAL_BACKEND=inline` |
| `memory` | `MemoryEventRepository` (proceso local, sin Docker/Postgres) | `EVAL_BACKEND=inline` |

`memory` es para demo/CI sin almacén: los datos viven en RAM y se pierden al reiniciar. Con BigQuery el worker no reclama jobs (`FOR UPDATE SKIP LOCKED` es de Postgres). El factory rechaza `bigquery` + `postgres` eval.

## Playground (dual model)

`POST /api/v1/playground/dual` corre el mismo prompt en dos modelos con `wrap_openai`.
Por defecto usa **Groq** (`OPENAI_BASE_URL=https://api.groq.com/openai/v1`, modelos
`openai/gpt-oss-20b` / `openai/gpt-oss-120b`). Requiere `OPENAI_API_KEY` = key de
https://console.groq.com/keys (o `JUDGE_API_KEY`) y el extra `openai`.
Los ids disponibles dependen de la cuenta; listá con la API de models de Groq.
La telemetría se reingesta en la misma API → FinOps / Traces.

Contratos en [`SPEC.md`](../../SPEC.md), sección 6–8. Configuración solo por variables de entorno.
