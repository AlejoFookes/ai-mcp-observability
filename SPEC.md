# SPEC — multiMCP

Estado: propuesta para aprobación. Fecha de corte de dependencias: 2026-11-14.
Producto: plataforma portable y versionada de observabilidad, FinOps y evaluación para pipelines de IA generativa, SDKs de proveedores y servidores MCP.

Este documento es la fuente de verdad. Un PR que se desvíe lo actualiza en el mismo cambio.

## 1. Objetivo

Un operador de un pipeline generativo puede:

1. Envolver un cliente `openai`, `anthropic` o `google-genai` y obtener tokens, TTFT, latencia total, costo estimado y errores, con `prompt_version` y `environment`.
2. Anteponer un proxy a un servidor MCP existente y medir uso por tool, latencia, bytes devueltos y errores JSON-RPC.
3. Consultar gasto, percentiles y trazas en un backend que corre con PostgreSQL dentro de Docker.
4. Encolar una evaluación RAG desacoplada de la respuesta del modelo.

El sistema es de un solo tenant en la versión `0.1`. No hay cuentas ni facturación propia.

## 2. Estructura del monorepo

```text
multiMCP-SDK/
├── SPEC.md
├── ROADMAP.md
├── README.md
├── LICENSE                          # MIT, se agrega en el Milestone 1
├── .gitignore
├── .cursor/rules/architecture.mdc
├── .github/
│   ├── workflows/ci.yml
│   ├── ISSUE_TEMPLATE/feature_task.md
│   └── PULL_REQUEST_TEMPLATE.md
├── sdks/python/                     # distribución multimcp 0.1.0
│   ├── pyproject.toml
│   ├── src/multimcp/
│   │   ├── __init__.py
│   │   ├── context.py               # contextvars
│   │   ├── models.py                # evento schema_version 1.0
│   │   ├── pricing/
│   │   │   ├── estimator.py
│   │   │   └── catalogs/2026-11-01.json
│   │   ├── exporters/
│   │   │   ├── base.py
│   │   │   ├── memory.py
│   │   │   └── http.py
│   │   └── instrument/
│   │       ├── openai.py
│   │       ├── anthropic.py
│   │       └── google_genai.py
│   └── tests/
├── services/proxy/                  # distribución multimcp-proxy
│   ├── pyproject.toml
│   ├── src/multimcp_proxy/
│   │   ├── cli.py
│   │   ├── framing.py               # JSON-RPC newline-delimited
│   │   ├── stdio.py
│   │   ├── streamable_http.py       # JSON o SSE por request
│   │   └── metrics.py
│   └── tests/
├── services/api/                    # distribución multimcp-api
│   ├── pyproject.toml
│   ├── alembic/
│   ├── src/multimcp_api/
│   │   ├── main.py
│   │   ├── settings.py
│   │   ├── errors.py
│   │   ├── schemas/
│   │   ├── api/v1/
│   │   ├── domain/
│   │   ├── repositories/
│   │   │   ├── base.py              # Protocol
│   │   │   ├── postgres.py
│   │   │   └── bigquery.py          # import perezoso
│   │   └── eval/
│   │       ├── worker.py
│   │       ├── judge.py
│   │       └── rubrics/rag_judge_1_0.txt
│   └── tests/
├── apps/web/                        # @multimcp/web
│   ├── package.json
│   └── src/
│       ├── api/
│       ├── pages/                   # FinOps, Latency, Traces, Compare
│       └── components/
└── deploy/
    ├── compose.yaml                 # postgres + api + worker + web
    ├── Dockerfile.api
    ├── Dockerfile.worker
    ├── Dockerfile.proxy
    └── Dockerfile.web
```

Los directorios de código se crean en el milestone que los implementa. Esta fase deja solo gobernanza.

## 3. Decisiones

### 3.1 Wrappers explícitos por instancia

`wrap_openai(client)`, `wrap_anthropic(client)` y `wrap_google(client)` reemplazan métodos del cliente que el usuario pasa. No hay monkeypatch del módulo. La llamada devuelve el mismo tipo que el SDK y, si el SDK lanza, la excepción original se relanza después de emitir el evento.

Costo: el usuario tiene que envolver el cliente. A cambio, una versión nueva del SDK no queda instrumentada en silencio, y dos clientes en el mismo proceso pueden exportar a destinos distintos.

### 3.2 Contrato propio, exporter HTTP

El evento canónico es JSON con `schema_version: "1.0"`. El exporter por defecto hace `POST /api/v1/events` con `httpx`.

OpenTelemetry queda fuera de `0.1`. Las convenciones semánticas GenAI no modelan `catalog_version`, `prompt_version` ni el tamaño del resultado de una tool MCP. Un exporter OTLP puede agregarse después sin cambiar el evento.

El SDK de instrumentación no comparte el cliente HTTP del proveedor. `openai` 3.x y `anthropic` 2.x hablan `httpx2`. Nuestro exporter habla `httpx`. Un cambio en el stack del proveedor no rompe la ingesta.

### 3.3 MCP revisión 2026-07-28

Spec de referencia: [2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28).

Transportes del proxy:

- **stdio.** El proxy lanza el servidor como subproceso. Mensajes JSON-RPC delimitados por newline en stdin/stdout. `stderr` se reenvía y no cuenta como error.
- **Streamable HTTP.** Un endpoint POST. La respuesta upstream es `application/json` o un stream `text/event-stream` acotado a ese request. El proxy retransmite los frames SSE y mide hasta el resultado JSON-RPC final.

La revisión 2026-07-28 retiró el handshake `initialize`, el header `Mcp-Session-Id` y el GET de sesión. La versión viaja en `_meta["io.modelcontextprotocol/protocolVersion"]`. El proxy no interpreta ese campo para enrutar: reenvía headers, `_meta` y body intactos, y lee `method` / `params.name` solo para la métrica.

El transporte HTTP+SSE de dos endpoints (revisión 2024-11-05) queda fuera de `0.1`. Implementarlo haría compatible un binding que la spec ya reemplazó.

El paquete `mcp` 2.3 se usa en tests si sus modelos coinciden con esta revisión. El runtime del proxy implementa el framing contra la spec, así que no queda atado a un atraso del SDK.

### 3.4 Cola de evaluación en PostgreSQL

`arq` 0.28 está en mantenimiento y exige Redis. El worker reclama filas de `eval_jobs` con `FOR UPDATE SKIP LOCKED`. El compose portable levanta un solo Postgres.

`EVAL_BACKEND=inline` ejecuta el juez con `starlette.background.BackgroundTasks` para tests y un proceso único. `EVAL_BACKEND=postgres` es el default del compose. Un fallo del proceso deja la fila en `queued` cuando expira `locked_at`.

### 3.5 Precio estimado en el cliente

El catálogo vive dentro del wheel de `multimcp`, en `pricing/catalogs/`. El SDK envía tokens, `estimated_cost_usd`, `catalog_version` y `price_status`. El backend persiste esos campos. No recalcula en `0.1`: la estimación y el catálogo que la produjo quedan juntos en el evento.

Una fila sin modelo deja `estimated_cost_usd = null` y `price_status = "unpriced"`. Cero sería una mentira contable.

### 3.6 Privacidad por defecto

El evento de inferencia y el evento MCP no incluyen prompt, completion ni body de la tool. Del resultado MCP se guarda `payload_bytes` (UTF-8 del objeto `result`). El texto de una evaluación existe solo si el cliente llama a `POST /api/v1/evaluations`.

### 3.7 PostgreSQL por defecto, BigQuery opcional

`STORAGE_BACKEND=postgres` usa el `Protocol` `EventRepository` implementado con SQLAlchemy 2 y asyncpg. `STORAGE_BACKEND=bigquery` importa `google.cloud.bigquery` dentro del adaptador. El imagen Docker de la API no necesita credenciales de GCP para arrancar.

## 4. SDK Python — `multimcp` 0.1.0

Ruta: `sdks/python`. Python `>=3.12`. Layout `src`. Build backend `hatchling`.

### 4.0 Gestión de paquetes con uv

`uv` instala, resuelve y ejecuta todo el Python del repo. No se usa `pip` ni `requirements.txt`.

- El `pyproject.toml` de la raíz es un workspace virtual de uv. Sus miembros son los paquetes bajo `sdks/` (y, desde la Fase 2, bajo `services/`).
- `.python-version` fija 3.12. `uv python install` lo lee.
- `uv.lock` se commitea. CI corre `uv sync --locked`: un lock desactualizado rompe el build en lugar de resolver otra cosa.
- El grupo `dev` de la raíz trae `pytest` y `ruff`, e instala los miembros del workspace en modo editable.
- La configuración de `ruff` y `pytest` vive en la raíz. Los dos comandos de verificación son `uv run ruff check .` y `uv run pytest`.

### 4.1 Dependencias

| Extra | Paquete | Rango | Uso |
| --- | --- | --- | --- |
| núcleo | `pydantic` | `>=2.9,<3` | Evento y catálogo |
| núcleo | `httpx` | `>=0.28,<1` | Exporter HTTP |
| `openai` | `openai` | `>=3.51,<4` | Wrapper |
| `anthropic` | `anthropic` | `>=2.8,<3` | Wrapper |
| `google` | `google-genai` | `>=3.3,<4` | Wrapper |
| `all` | los tres extras | | |
| `dev` | `pytest`, `ruff` | | CI |

Los wrappers importan el SDK del proveedor dentro de la función. Si el extra no está instalado, lanzan `MultimcpConfigError` con el nombre del extra. El import de `multimcp` no importa `openai`, `anthropic` ni `google.genai`.

### 4.2 Superficie pública

```python
from multimcp import (
    configure,
    prompt_context,
    wrap_openai,
    wrap_anthropic,
    wrap_google,
)

configure(exporter=..., catalog_version="2026-11-01")

with prompt_context(prompt_version="checkout-v3", environment="staging", trace_id="..."):
    response = wrap_openai(client).responses.create(model="...", input="...")
```

`prompt_context` escribe `contextvars`. Fuera del bloque, `prompt_version` es null y `environment` sale de `MULTIMCP_ENVIRONMENT` (default `local`). Si no hay `trace_id`, el wrapper genera un UUID por llamada.

### 4.3 Métodos que se instrumentan

**OpenAI** (`OpenAI` y `AsyncOpenAI`), guía de la lib 3.51:

- `client.responses.create`. API primaria. Con `stream=True`, TTFT en el primer evento `response.output_text.delta`. Tokens en el evento `response.completed`: `usage.input_tokens`, `usage.output_tokens`.
- `client.chat.completions.create`. API todavía soportada. `usage.prompt_tokens` → `input_tokens`, `usage.completion_tokens` → `output_tokens`. En stream, el wrapper no fuerza `stream_options`; si el último chunk trae `usage`, lo copia. Si el stream corta antes, los tokens quedan null.

**Anthropic** (`Anthropic` y `AsyncAnthropic`), lib 2.8:

- `client.messages.create`.
- `client.messages.create(..., stream=True)` y `client.messages.stream(...)`.
- Tokens: `usage.input_tokens`, `usage.output_tokens`, `usage.cache_read_input_tokens`. `cache_creation_input_tokens` se suma al input facturable solo si el catálogo tiene columna de creación; si no, viaja en `metadata` y el costo de creación queda `unpriced` en esa componente.
- TTFT en el primer `content_block_delta` (stream crudo) o en el primer evento `text` (helper `stream()`).

**Google Gen AI** (`google.genai.Client`), lib 3.3. Se instrumenta el cliente de la Gemini Developer API. El cliente `enterprise=True` (Agent Platform / Vertex) queda fuera de `0.1`.

- `client.models.generate_content` y `client.models.generate_content_stream`.
- Los mismos métodos en `client.aio.models`.
- `usage_metadata.prompt_token_count` → `input_tokens`.
- `usage_metadata.candidates_token_count` → `output_tokens`.
- `usage_metadata.thoughts_token_count` → `reasoning_tokens` cuando el atributo existe.
- `usage_metadata.cached_content_token_count` → `cache_read_tokens`.
- TTFT en el primer chunk del stream que trae texto.

`operation` vale `responses.create`, `chat.completions.create`, `messages.create`, `messages.stream` o `models.generate_content`.

### 4.4 Evento `schema_version` 1.0

```json
{
  "schema_version": "1.0",
  "event_id": "uuid",
  "occurred_at": "2026-11-14T15:04:05.123Z",
  "environment": "staging",
  "sdk_name": "multimcp",
  "sdk_version": "0.1.0",
  "provider": "openai",
  "model": "gpt-5.5",
  "operation": "responses.create",
  "prompt_version": "checkout-v3",
  "trace_id": "uuid",
  "span_id": "uuid",
  "parent_span_id": null,
  "input_tokens": 120,
  "output_tokens": 40,
  "reasoning_tokens": 0,
  "cache_read_tokens": 0,
  "cache_write_tokens": 0,
  "ttft_ms": 180.4,
  "latency_ms": 940.2,
  "estimated_cost_usd": "0.00123400",
  "catalog_version": "2026-11-01",
  "price_status": "priced",
  "status": "ok",
  "error_type": null,
  "metadata": {}
}
```

Conteo de tokens, igual para los tres proveedores:

- `input_tokens` es el input total, incluidas las lecturas y escrituras de caché.
- `output_tokens` es el output facturado total, incluido el razonamiento.
- `reasoning_tokens`, `cache_read_tokens` y `cache_write_tokens` son desgloses de esos totales. No se suman encima.

Cada wrapper traduce el `usage` del proveedor a esa forma. Anthropic informa las lecturas y escrituras de caché fuera de `input_tokens`, y el wrapper las suma. Google informa `thoughts_token_count` fuera de `candidates_token_count`, y el wrapper lo suma al output.

El evento rechaza campos desconocidos y timestamps sin zona horaria. `estimated_cost_usd` está presente si y solo si `price_status = priced`. `error_type` está presente si y solo si `status = error`.

`provider` es `openai` | `anthropic` | `google`. `status` es `ok` | `error`. `price_status` es `priced` | `unpriced`. `ttft_ms` es null cuando la llamada no es stream. `latency_ms` usa `time.perf_counter` en el proceso del SDK. `estimated_cost_usd` es string decimal en el JSON para no perder precisión; en Python es `decimal.Decimal`.

`error_type` es el nombre de la clase de la excepción (`APIStatusError`, `APITimeoutError`, …). El mensaje de la excepción no se envía: suele contener fragmentos del request.

`metadata` acepta un objeto plano string→escalar, con un máximo de 16 claves de hasta 64 caracteres y valores string de hasta 128 caracteres. El juez escribe `role=judge` y `rubric_version`.

### 4.5 Exporters

```text
Exporter.insert(events: Sequence[GenAIEvent | McpEvent]) -> None
```

- `MemoryExporter` guarda eventos en una lista. Es el default de tests.
- `HttpExporter` postea a `MULTIMCP_INGEST_URL` (default `http://localhost:8000`) con `Authorization: Bearer $MULTIMCP_INGEST_TOKEN`. Sin token, no manda el header. Timeout 2 segundos. Un lote tiene como máximo 100 eventos. Los `GenAIEvent` van a `/api/v1/events` y los `McpEvent` a `/api/v1/mcp-events`. Si el POST falla, registra el nombre del error con el logger `multimcp` y descarta el lote. Hay un buffer en memoria de 1 000 eventos; al llenarse, descarta los más viejos.
- `insert` solo encola. Un hilo daemon envía cada segundo, o antes si hay un lote completo. `flush()` envía lo pendiente desde el hilo que llama, y `close()` (registrado en `atexit`) detiene el hilo y drena el buffer.

`configure(exporter=...)` fija el exporter del proceso, y `wrap_*(client, exporter=...)` lo pisa para un cliente. Sin `configure`, si `MULTIMCP_INGEST_URL` está seteada se crea un `HttpExporter`; si no, el evento se descarta con un log de nivel debug.

La telemetría es fail-open. Nunca se reintenta, y el hilo del usuario no espera a la red. Una excepción del exporter se registra y no llega al código del usuario.

### 4.6 Catálogo de precios

Archivo: `sdks/python/src/multimcp/pricing/catalogs/2026-11-01.json`.

```json
{
  "catalog_version": "2026-11-01",
  "currency": "USD",
  "entries": [
    {
      "provider": "openai",
      "model": "gpt-5.5",
      "input_per_million": "5.00",
      "output_per_million": "30.00",
      "cache_read_per_million": "0.50",
      "max_input_tokens": 272000,
      "source_url": "https://developers.openai.com/api/docs/pricing",
      "retrieved_on": "2026-11-14"
    }
  ]
}
```

Cada fila copia la tarifa estándar de la página pública del proveedor y cita `source_url` y la fecha de lectura (`retrieved_on`). El archivo es dato, no código. Los precios son strings: un float JSON invalida el archivo porque no parsea como decimal exacto.

El catálogo `2026-11-01` trae filas de OpenAI y Anthropic. No trae filas de Google: la página de precios de Gemini no se pudo leer al armarlo, y una tarifa sin fuente queda fuera. Los eventos de Gemini salen `unpriced` hasta que un catálogo nuevo cite la página.

`max_input_tokens` marca el techo de una tarifa por tramos (OpenAI ≤272K, Claude Haiku 5.5 ≤100K). Por encima del techo, la llamada queda `unpriced`. No se aplica la tarifa corta a un prompt largo.

Fórmula, con `Decimal` y redondeo `ROUND_HALF_EVEN` a 8 decimales:

```text
cost = ((input_tokens - cache_read_tokens) * input_per_million
      + cache_read_tokens * cache_read_per_million
      + output_tokens * output_per_million) / 1_000_000
```

El razonamiento ya está dentro de `output_tokens` y se cobra a tarifa de output en los tres proveedores. La llamada queda `unpriced`, con costo null, cuando:

- el modelo no tiene fila (el match es exacto; solo se ignora el prefijo `models/` de Google, y un snapshot fechado no hereda la tarifa del alias),
- faltan `input_tokens` u `output_tokens`, por ejemplo en un stream cortado,
- `input_tokens` supera `max_input_tokens`,
- hubo lecturas de caché y la fila no tiene `cache_read_per_million`,
- hubo escrituras de caché. Ningún catálogo `0.1` tiene columna de escritura, y OpenAI y Anthropic las cobran aparte.

No se mezcla una estimación parcial con un null silencioso. Batch, Fast mode, endpoints regionales e `inference_geo` no se modelan: el costo es el de la tarifa estándar global.

`currency` distinto de `USD` invalida el archivo al cargarlo, igual que un `provider/model` repetido o un `catalog_version` que no coincide con el nombre del archivo.

## 5. Proxy MCP — `multimcp-proxy`

### 5.1 CLI

```text
multimcp-proxy stdio --server-name filesystem -- python -m mcp_server_filesystem
multimcp-proxy http --server-name docs --listen 127.0.0.1:8080 --upstream http://127.0.0.1:3000/mcp
```

El proxy depende de `multimcp` para el exporter y el modelo de evento. No abre sockets de red hacia el proveedor del modelo.

### 5.2 Evento MCP `schema_version` 1.0

```json
{
  "schema_version": "1.0",
  "event_id": "uuid",
  "occurred_at": "2026-11-14T15:04:05.123Z",
  "environment": "local",
  "server_name": "filesystem",
  "transport": "stdio",
  "method": "tools/call",
  "tool_name": "read_file",
  "jsonrpc_id": "1",
  "latency_ms": 12.5,
  "payload_bytes": 4096,
  "status": "ok",
  "error_code": null,
  "error_type": null,
  "trace_id": "uuid"
}
```

`transport` es `stdio` | `streamable_http`. `tool_name` sale de `params.name` cuando `method` es `tools/call`; en otro método es null. `payload_bytes` es `len(json.dumps(result).encode("utf-8"))` del resultado final. Los frames SSE de progreso no se suman. `error_code` es el entero JSON-RPC (`-32603`, `-32602`, …) cuando la respuesta trae `error`. Un proceso que muere o un upstream que corta el stream marca `status=error`, `error_type=transport` y `error_code=null`.

Se registran todos los métodos. El agregado "frecuencia de tool" filtra `method = tools/call`.

El proxy no modifica `id`, `method`, `params`, `_meta` ni `result`.

### 5.3 Qué cuenta como fallo

| Condición | status | error_type |
| --- | --- | --- |
| Respuesta JSON-RPC con `result` | ok | null |
| Respuesta JSON-RPC con `error` | error | jsonrpc |
| Línea stdout que no es JSON | error | framing |
| Subproceso termina a mitad de un request | error | transport |
| Upstream HTTP no es 200, o el stream SSE se corta antes del result | error | transport |

Una notificación no tiene latencia de request. Se reenvía y no genera fila, salvo `notifications/message` que tampoco genera fila: el proxy no convierte logs del servidor en métricas de tool.

## 6. Backend — `multimcp-api`

Python `>=3.12`. ASGI con `uvicorn`. Configuración solo por entorno, leída con Pydantic Settings.

| Variable | Default | Rol |
| --- | --- | --- |
| `STORAGE_BACKEND` | `postgres` | `postgres` \| `bigquery` |
| `DATABASE_URL` | `postgresql+asyncpg://multimcp:multimcp@localhost:5432/multimcp` | App |
| `ALEMBIC_DATABASE_URL` | la misma URL con driver `psycopg` | Migraciones |
| `INGEST_TOKEN` | vacío, la API rechaza writes | Bearer compartido de un solo tenant |
| `EVAL_BACKEND` | `postgres` | `postgres` \| `inline` |
| `JUDGE_BASE_URL` | `https://api.openai.com/v1` | Endpoint OpenAI-compatible |
| `JUDGE_MODEL` | vacío | Modelo del juez |
| `JUDGE_API_KEY` | vacío | No se loguea |
| `BQ_PROJECT` | vacío | Solo con BigQuery |
| `BQ_DATASET` | `multimcp` | Solo con BigQuery |

`INGEST_TOKEN` vacío hace que todo POST responda 401. El compose de desarrollo inyecta un token por variable de entorno, nunca por un default en código.

### 6.1 Dependencias

| Paquete | Rango | Rol |
| --- | --- | --- |
| `fastapi` | `>=0.162,<1` | HTTP. Python `>=3.11`; el repo fija 3.12 |
| `uvicorn[standard]` | `>=0.32,<1` | ASGI |
| `pydantic` / `pydantic-settings` | `>=2.9,<3` | Contratos y env |
| `sqlalchemy` | `>=2.0,<3` | Repositorio Postgres |
| `alembic` | `>=1.14,<2` | Migraciones |
| `asyncpg` | `>=0.30,<1` | Runtime async |
| `psycopg[binary]` | `>=3.2,<4` | Alembic en modo sync |
| `multimcp` | el paquete del monorepo | Modelos de evento y catálogo de lectura |
| extra `judge` | `openai>=3.51,<4` | Juez vía Responses API |
| extra `bigquery` | `google-cloud-bigquery>=3.25,<4` | Adaptador opcional |
| `dev` | `pytest`, `pytest-asyncio`, `httpx`, `ruff` | CI |

Alembic usa `psycopg` porque su runner es sync. La app usa `asyncpg`. Las dos URLs salen de la misma configuración.

### 6.2 Sobre de error

Toda respuesta de error:

```json
{
  "schema_version": "1.0",
  "error": {
    "code": "validation_error",
    "message": "schema_version must be 1.0",
    "details": []
  }
}
```

`code`: `unauthorized` (401), `validation_error` (422), `not_found` (404), `payload_too_large` (413), `storage_unavailable` (503). Un 500 no incluye el traceback.

### 6.3 Endpoints

Prefijo `/api/v1`. Writes exigen `Authorization: Bearer <INGEST_TOKEN>`. En `0.1` los GET usan el mismo token.

Ventana temporal obligatoria en las consultas, formato ISO-8601, máximo 31 días. `from` inclusivo, `to` exclusivo.

**`GET /api/v1/health`**

```json
{ "schema_version": "1.0", "status": "ok", "storage_backend": "postgres" }
```

No exige token. No abre una query pesada: ejecuta `SELECT 1` o, en BigQuery, un no-op de configuración. Si el almacén no responde, `status` es `degraded` y el HTTP sigue siendo 200 para que Compose distinga "proceso vivo" de "almacén listo" vía el body. El readiness estricto es `GET /api/v1/health?ready=true`, que responde 503 si el `SELECT 1` falla.

**`POST /api/v1/events`** y **`POST /api/v1/mcp-events`**

Body: `{ "schema_version": "1.0", "events": [ ... ] }`. Máximo 100 eventos y 1 MiB. `event_id` es la clave de idempotencia. Un id ya visto cuenta como duplicado y no pisa la fila.

```json
{ "schema_version": "1.0", "accepted": 98, "duplicates": 2 }
```

HTTP 200.

**`GET /api/v1/finops/summary`**

Query: `from`, `to`, `group_by=model|provider|prompt_version|mcp_server`, `include_judge=false`.

`include_judge=false` excluye eventos con `metadata.role = judge`. El gasto del juez se pide con `include_judge=true` y no se mezcla con el gasto del producto.

```json
{
  "schema_version": "1.0",
  "currency": "USD",
  "rows": [
    {
      "key": "openai/gpt-5.5",
      "request_count": 10,
      "error_count": 1,
      "input_tokens": 1000,
      "output_tokens": 400,
      "estimated_cost_usd": "0.01200000",
      "unpriced_count": 0
    }
  ]
}
```

`group_by=mcp_server` lee `mcp_events` y deja los campos de tokens y costo en cero: una tool no tiene tarifa de modelo. El gasto de modelos y el volumen MCP se muestran en filas distintas, no sumados.

**`GET /api/v1/latency`**

Query: `from`, `to`, `group_by=model|operation|mcp_tool`.

```json
{
  "schema_version": "1.0",
  "rows": [
    { "key": "openai/gpt-5.5", "count": 10, "p50_ms": 800.0, "p95_ms": 2100.0, "error_rate": 0.1 }
  ]
}
```

PostgreSQL:

```sql
percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms
```

BigQuery:

```sql
APPROX_QUANTILES(latency_ms, 100)[OFFSET(50)] AS p50_ms,
APPROX_QUANTILES(latency_ms, 100)[OFFSET(95)] AS p95_ms
```

`error_rate` es `error_count / count` sobre la misma población. Los percentiles incluyen llamadas con error: la latencia hasta el fallo es parte del síntoma.

**`GET /api/v1/traces/{trace_id}`**

Une `genai_events` y `mcp_events` con ese `trace_id`, ordenados por `occurred_at`. 404 si no hay filas.

**`GET /api/v1/compare`**

Query: `from`, `to`, `dimension=prompt_version|model`, `left`, `right`.

Devuelve dos snapshots con las mismas medidas de FinOps y de latencia. La dimensión `model` compara `provider/model`. No hay test estadístico en `0.1`: el comparador muestra los dos lados y el conteo, para que una muestra de 3 requests no parezca una conclusión.

**`POST /api/v1/evaluations`**

```json
{
  "schema_version": "1.0",
  "rubric_version": "rag-judge-1.0",
  "trace_id": "uuid-or-null",
  "query": "texto",
  "contexts": ["fragmento"],
  "answer": "texto"
}
```

Límites: `query` y `answer` hasta 16 KiB cada uno, hasta 20 `contexts`, 64 KiB en total. HTTP 202:

```json
{ "schema_version": "1.0", "job_id": "uuid", "status": "queued" }
```

**`GET /api/v1/evaluations/{job_id}`** devuelve el job. **`GET /api/v1/pricing/catalog`** devuelve `catalog_version`, `currency` y la lista de `provider/model` sin exigir que el backend recalcule.

### 6.4 Repositorio

```python
class EventRepository(Protocol):
    async def insert_genai(self, events: Sequence[GenAIEvent]) -> InsertResult: ...
    async def insert_mcp(self, events: Sequence[McpEvent]) -> InsertResult: ...
    async def finops_summary(self, query: WindowQuery) -> list[FinOpsRow]: ...
    async def latency(self, query: WindowQuery) -> list[LatencyRow]: ...
    async def get_trace(self, trace_id: str) -> list[TraceSpan]: ...
    async def compare(self, query: CompareQuery) -> CompareResult: ...
    async def enqueue_eval(self, job: EvalJob) -> None: ...
    async def claim_eval_jobs(self, limit: int, lock_seconds: int) -> list[EvalJob]: ...
    async def complete_eval(self, job_id: UUID, outcome: EvalOutcome) -> None: ...
```

Los routers dependen de este `Protocol`. `repositories/bigquery.py` importa `google.cloud.bigquery` en el constructor. Con `STORAGE_BACKEND=postgres` ese módulo no se importa.

## 7. Esquema PostgreSQL

Migración Alembic `0001_init`. Tipos monetarios en `numeric(18, 8)`. Tiempos en `timestamptz`.

```sql
CREATE TABLE genai_events (
    event_id            uuid PRIMARY KEY,
    schema_version      text NOT NULL,
    received_at         timestamptz NOT NULL DEFAULT now(),
    occurred_at         timestamptz NOT NULL,
    environment         text NOT NULL,
    sdk_name            text NOT NULL,
    sdk_version         text NOT NULL,
    provider            text NOT NULL,
    model               text NOT NULL,
    operation           text NOT NULL,
    prompt_version      text,
    trace_id            text NOT NULL,
    span_id             text NOT NULL,
    parent_span_id      text,
    input_tokens        integer,
    output_tokens       integer,
    reasoning_tokens    integer,
    cache_read_tokens   integer,
    cache_write_tokens  integer,
    ttft_ms             double precision,
    latency_ms          double precision NOT NULL,
    estimated_cost_usd  numeric(18, 8),
    catalog_version     text,
    price_status        text NOT NULL,
    status              text NOT NULL,
    error_type          text,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT genai_price_status CHECK (price_status IN ('priced', 'unpriced')),
    CONSTRAINT genai_status CHECK (status IN ('ok', 'error'))
);

CREATE INDEX genai_events_occurred_idx ON genai_events (occurred_at DESC);
CREATE INDEX genai_events_trace_idx ON genai_events (trace_id);
CREATE INDEX genai_events_model_idx ON genai_events (provider, model, occurred_at DESC);
CREATE INDEX genai_events_prompt_idx ON genai_events (prompt_version, occurred_at DESC);

CREATE TABLE mcp_events (
    event_id        uuid PRIMARY KEY,
    schema_version  text NOT NULL,
    received_at     timestamptz NOT NULL DEFAULT now(),
    occurred_at     timestamptz NOT NULL,
    environment     text NOT NULL,
    server_name     text NOT NULL,
    transport       text NOT NULL,
    method          text NOT NULL,
    tool_name       text,
    jsonrpc_id      text,
    latency_ms      double precision NOT NULL,
    payload_bytes   integer NOT NULL,
    status          text NOT NULL,
    error_code      integer,
    error_type      text,
    trace_id        text NOT NULL,
    CONSTRAINT mcp_transport CHECK (transport IN ('stdio', 'streamable_http')),
    CONSTRAINT mcp_status CHECK (status IN ('ok', 'error'))
);

CREATE INDEX mcp_events_occurred_idx ON mcp_events (occurred_at DESC);
CREATE INDEX mcp_events_tool_idx ON mcp_events (server_name, tool_name, occurred_at DESC);
CREATE INDEX mcp_events_trace_idx ON mcp_events (trace_id);

CREATE TABLE eval_jobs (
    job_id                uuid PRIMARY KEY,
    schema_version        text NOT NULL,
    status                text NOT NULL,
    rubric_version        text NOT NULL,
    judge_model           text,
    trace_id              text,
    query                 text NOT NULL,
    contexts              jsonb NOT NULL,
    answer                text NOT NULL,
    context_relevance     double precision,
    hallucination_label   text,
    rationale             text,
    error_message         text,
    attempt               integer NOT NULL DEFAULT 0,
    created_at            timestamptz NOT NULL DEFAULT now(),
    started_at            timestamptz,
    finished_at           timestamptz,
    locked_at             timestamptz,
    CONSTRAINT eval_status CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    CONSTRAINT eval_label CHECK (
        hallucination_label IS NULL
        OR hallucination_label IN ('supported', 'partial', 'unsupported')
    )
);

CREATE INDEX eval_jobs_claim_idx ON eval_jobs (status, locked_at);
```

Claim del worker:

```sql
UPDATE eval_jobs
SET status = 'running', started_at = now(), locked_at = now() + make_interval(secs => $2), attempt = attempt + 1
WHERE job_id IN (
    SELECT job_id FROM eval_jobs
    WHERE status = 'queued' OR (status = 'running' AND locked_at < now())
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT $1
)
RETURNING *;
```

Tres intentos. Al cuarto fallo, `status = failed`.

### 7.1 BigQuery

Mismas columnas lógicas. `genai_events` y `mcp_events` particionadas por `DATE(occurred_at)` y clusterizadas por `provider, model` y `server_name, tool_name`. Inserción por streaming insert con `event_id` como `insertId`. `eval_jobs` también existe en BigQuery, pero el worker de `0.1` reclama jobs solo en PostgreSQL. Con `STORAGE_BACKEND=bigquery` el evaluador queda en `EVAL_BACKEND=inline` y el README lo dice. Una cola transaccional en BigQuery no es parte de `0.1`.

## 8. Evaluador RAG

El juez responde una sola pregunta: si `answer` se sostiene en `contexts` para esa `query`. No contrasta contra conocimiento del mundo. Una afirmación material sin apoyo en los fragmentos es `unsupported`. Mezcla de afirmaciones sostenidas y no sostenidas es `partial`. Respuesta contenida en los fragmentos es `supported`.

`context_relevance` es un float de 0 a 1: qué fracción de los fragmentos aportaba a la query. No es un score de retrieval del índice, porque este servicio no ve el índice.

Rúbrica versionada `rag-judge-1.0` en `services/api/src/multimcp_api/eval/rubrics/rag_judge_1_0.txt`. El archivo es el prompt. La salida exigida es JSON:

```json
{
  "context_relevance": 0.0,
  "hallucination_label": "supported",
  "rationale": "hasta 500 caracteres"
}
```

Cliente: extra `judge`, paquete `openai`, `client.responses.create` con `base_url=JUDGE_BASE_URL`. Así el mismo código habla con la API de OpenAI, con un endpoint compatible de Gemini o con un servidor local. `temperature` 0. El resultado se valida con Pydantic. JSON inválido se reintenta una vez y después el job queda `failed`.

La llamada del juez pasa por `wrap_openai` con `metadata.role = judge` y `metadata.rubric_version = rag-judge-1.0`, para que FinOps pueda separarla. El worker no espera esa llamada dentro del request que hizo el usuario: el POST ya respondió 202.

## 9. Frontend — `apps/web`

| Paquete | Rango de referencia al 2026-11-14 | Rol |
| --- | --- | --- |
| `react`, `react-dom` | 19 | UI |
| `vite` | 8 | Build. Exige Node 20.19+ o 22.12+. CI usa Node 22 |
| `@vitejs/plugin-react` | 6 | Plugin |
| `typescript` | 5.6 o superior, el que fije `npm create vite` | `strict`, `noUncheckedIndexedAccess` |
| `@tanstack/react-query` | 5 | Estado de servidor, cache y reintento de GET |
| `react-router` | 7 | Rutas |
| `recharts` | 3 | Series de gasto y latencia |
| `tailwindcss` | 4 | Tokens visuales, sin librería de componentes |

El script `"build"` es `tsc -b && vite build`. El cliente HTTP es `fetch` tipado a mano contra los JSON de la sección 6.3. OpenAPI codegen queda fuera de `0.1`; los tipos del front y los modelos Pydantic se revisan en el mismo PR cuando cambia un contrato.

Pantallas:

1. **FinOps.** Gasto por modelo, por `prompt_version` y volumen por servidor MCP. Filtro de fechas y toggle de gasto del juez.
2. **Latencia.** `p50` y `p95` por modelo, operación y tool MCP, más `error_rate`.
3. **Trazas.** Buscador por `trace_id` y línea de tiempo de spans GenAI y MCP.
4. **Comparar.** Dos `prompt_version` o dos modelos, lado a lado, con el conteo de muestras visible.

El token de lectura vive en `sessionStorage`, cargado desde un campo de la UI. No se escribe en el bundle.

## 10. Docker

`deploy/compose.yaml` levanta `postgres:16`, `api`, `worker` y `web`. El worker es la misma imagen que la API con comando `python -m multimcp_api.eval.worker`. El proxy no entra en el compose por defecto: es un proceso al lado del servidor MCP del usuario, y el README muestra el comando `stdio`.

El servicio `api` publica `8000`. `web` publica `5173` en desarrollo y sirve el build estático en el compose. `STORAGE_BACKEND=postgres`. No hay servicio Redis.

## 11. CI

`.github/workflows/ci.yml`:

- `astral-sh/setup-uv`, Python desde `.python-version`, `uv sync --locked`, `uv run ruff check .` y `uv run pytest` en la raíz del workspace.
- Node 22, `npm ci` y `npm run build` cuando exista `apps/web/package.json`.
- Los tests no llaman a OpenAI, Anthropic, Google ni BigQuery. Los wrappers se prueban con clientes falsos. El HTTP del exporter se prueba con `httpx.MockTransport`. El repositorio Postgres de integración usa un test que se salta si no hay `DATABASE_URL` de test; el default de CI en `0.1` es el repositorio en memoria que implementa el mismo `Protocol`.

## 12. Fuera de alcance de 0.1

- Cuentas, organizaciones y facturación propia.
- Guardar prompts, completions o bodies de tools en la ingesta normal.
- Monkeypatch global y auto-instrumentación por `sitecustomize`.
- OpenTelemetry / OTLP.
- Transporte HTTP+SSE de la revisión 2024-11-05.
- Cliente Google `enterprise=True`.
- Cola de evaluación sobre BigQuery, Redis o `arq`.
- Test de significancia en el comparador.
- Codegen OpenAPI.

## 13. Referencias

- MCP 2026-07-28, transportes: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports
- MCP Streamable HTTP: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
- MCP stdio: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio
- OpenAI Python SDK: https://github.com/openai/openai-python
- Anthropic Python SDK: https://github.com/anthropics/anthropic-sdk-python
- Google Gen AI Python SDK: https://github.com/googleapis/python-genai
- FastAPI: https://fastapi.tiangolo.com
- SQLAlchemy 2: https://docs.sqlalchemy.org/en/20/
- TanStack Query: https://tanstack.com/query/latest
