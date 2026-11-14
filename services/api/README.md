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

Con BigQuery el worker no reclama jobs (`FOR UPDATE SKIP LOCKED` es de Postgres). El README y el factory rechazan `bigquery` + `postgres` eval.

Contratos en [`SPEC.md`](../../SPEC.md), sección 6–8. Configuración solo por variables de entorno.
