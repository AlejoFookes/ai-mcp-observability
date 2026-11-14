# ROADMAP — multiMCP

Cuatro fases. Cada tarea es un issue listo para crear con `gh`. No los crees hasta que `SPEC.md` esté aprobado: el cuerpo cita decisiones que todavía pueden cambiar.

Fuente de verdad del comportamiento: [`SPEC.md`](SPEC.md).

El remote tiene que existir y `gh auth status` tiene que estar verde. Desde la raíz del repo, en PowerShell:

```powershell
gh label create "milestone:m1" --color "1D76DB" --description "Fase 1 — SDK y catálogo de precios"
gh label create "milestone:m2" --color "5319E7" --description "Fase 2 — Proxy MCP"
gh label create "milestone:m3" --color "0E8A16" --description "Fase 3 — API, storage y evaluador"
gh label create "milestone:m4" --color "FBCA04" --description "Fase 4 — Dashboard y Compose"
gh label create "area:sdk" --color "0052CC" --description "Paquete multimcp"
gh label create "area:pricing" --color "006B75" --description "Catálogo de precios"
gh label create "area:proxy" --color "5319E7" --description "Proxy MCP"
gh label create "area:api" --color "B60205" --description "FastAPI"
gh label create "area:storage" --color "0E8A16" --description "Repositorios Postgres y BigQuery"
gh label create "area:eval" --color "D93F0B" --description "Evaluador RAG"
gh label create "area:web" --color "1D76DB" --description "Dashboard React"
gh label create "area:infra" --color "333333" --description "Docker, CI, empaquetado"
```

Si el label ya existe, `gh` responde error y se sigue con el siguiente.

## Fase 1 — Core SDK y tabla de precios versionada

Cierra el paquete `multimcp` `0.1.0`: evento `schema_version` 1.0, catálogo, exporters y wrappers de OpenAI, Anthropic y Google. Sin backend.

### M1.1 Scaffold del paquete

Labels: `milestone:m1`, `area:sdk`, `area:infra`

Criterios de aceptación:

- `sdks/python/pyproject.toml` declara `name = "multimcp"`, `version = "0.1.0"`, `requires-python = ">=3.12"` y build `hatchling`.
- Extras `openai`, `anthropic`, `google`, `all` y `dev` como en SPEC §4.1.
- `src/multimcp/__init__.py` exporta la versión. Importar `multimcp` no importa los SDK de proveedores.
- `ruff check sdks/python` y `pytest sdks/python/tests` pasan. Hay un test de import.
- `LICENSE` MIT en la raíz.

```powershell
gh issue create --title "M1.1 Scaffold del paquete multimcp 0.1.0" --label "milestone:m1,area:sdk,area:infra" --body @"
## Contexto
Crear el paquete instalable antes de los wrappers. SPEC §2 y §4.1.

## Criterios de aceptación
- [ ] ``sdks/python/pyproject.toml`` con ``multimcp`` ``0.1.0``, Python ``>=3.12`` y hatchling
- [ ] Extras ``openai``, ``anthropic``, ``google``, ``all`` y ``dev`` según SPEC §4.1
- [ ] ``import multimcp`` no importa openai, anthropic ni google.genai
- [ ] ``ruff check`` y ``pytest`` en verde, con un test de import
- [ ] ``LICENSE`` MIT en la raíz
"@
```

### M1.2 Contrato de evento y contexto

Labels: `milestone:m1`, `area:sdk`

Criterios de aceptación:

- Modelo Pydantic del evento GenAI de SPEC §4.4, `schema_version` literal `"1.0"`.
- `prompt_context` escribe `prompt_version`, `environment` y `trace_id` en `contextvars`.
- `environment` cae a `MULTIMCP_ENVIRONMENT` y, si no está, a `local`.
- Sin `trace_id`, cada llamada recibe un UUID nuevo.

```powershell
gh issue create --title "M1.2 Contrato de evento 1.0 y prompt_context" --label "milestone:m1,area:sdk" --body @"
## Contexto
El evento canónico y el contexto de correlación. SPEC §4.2 y §4.4.

## Criterios de aceptación
- [ ] Modelo Pydantic del evento GenAI con ``schema_version`` literal ``1.0``
- [ ] ``prompt_context`` publica prompt_version, environment y trace_id por contextvars
- [ ] environment default: ``MULTIMCP_ENVIRONMENT`` y después ``local``
- [ ] Sin trace_id, la llamada genera un UUID
- [ ] Tests del modelo rechazan un schema_version distinto
"@
```

### M1.3 Catálogo de precios y estimador

Labels: `milestone:m1`, `area:pricing`

Criterios de aceptación:

- `pricing/catalogs/2026-11-01.json` valida al cargar. `currency` distinta de `USD` falla.
- Cada fila tiene `source_url` y precios copiados de la página pública del proveedor en la fecha del catálogo. Sin filas inventadas.
- La fórmula de SPEC §4.6 usa `Decimal`. Modelo ausente, o componente sin tarifa, produce `price_status=unpriced` y costo null.
- Test de redondeo a 8 decimales y test de modelo desconocido.

```powershell
gh issue create --title "M1.3 Catálogo de precios 2026-11-01 y estimador Decimal" --label "milestone:m1,area:pricing" --body @"
## Contexto
El costo estimado viaja con el evento y con la versión del catálogo. SPEC §3.5 y §4.6.

## Criterios de aceptación
- [ ] ``pricing/catalogs/2026-11-01.json`` dentro del wheel
- [ ] Cada fila cita ``source_url``. Los precios salen de la página pública, no de un valor inventado
- [ ] ``currency`` distinta de USD invalida el archivo
- [ ] Modelo ausente o componente sin tarifa: costo null y ``price_status=unpriced``
- [ ] Tests de Decimal a 8 decimales, sin red
"@
```

### M1.4 Exporters

Labels: `milestone:m1`, `area:sdk`

Criterios de aceptación:

- `MemoryExporter` e `HttpExporter` cumplen `Exporter.insert`.
- HTTP postea a `MULTIMCP_INGEST_URL` con Bearer `MULTIMCP_INGEST_TOKEN`, lotes de hasta 100, timeout 2s.
- Un POST fallido se loguea y se descarta. Buffer máximo 1 000 eventos.
- Test con `httpx.MockTransport`. Ningún test abre un socket real.

```powershell
gh issue create --title "M1.4 Exporters de memoria y HTTP fail-open" --label "milestone:m1,area:sdk" --body @"
## Contexto
La telemetría no puede romper la llamada al modelo. SPEC §3.2 y §4.5.

## Criterios de aceptación
- [ ] ``MemoryExporter`` y ``HttpExporter``
- [ ] POST Bearer, lotes de 100, timeout 2s, buffer de 1000 con descarte de los más viejos
- [ ] Fallo de red logueado y descartado, sin relanzar
- [ ] Test con ``httpx.MockTransport``
"@
```

### M1.5 Wrappers de los tres SDK

Labels: `milestone:m1`, `area:sdk`

Criterios de aceptación:

- `wrap_openai` cubre `responses.create` y `chat.completions.create`, sync y async, unary y stream.
- `wrap_anthropic` cubre `messages.create` y `messages.stream`, sync y async.
- `wrap_google` cubre `models.generate_content` y `generate_content_stream` en el cliente sync y en `client.aio.models`. El cliente `enterprise=True` no se instrumenta.
- TTFT null fuera de stream. En stream, TTFT en el primer delta de texto definido en SPEC §4.3.
- Tokens mapeados a `input_tokens`, `output_tokens`, `reasoning_tokens` y `cache_read_tokens`.
- Si el método envuelto lanza, el evento queda `status=error` con `error_type` igual al nombre de la clase, y la misma excepción se relanza.
- Clientes falsos en tests. Cero llamadas de red.

```powershell
gh issue create --title "M1.5 Wrappers OpenAI, Anthropic y Google GenAI" --label "milestone:m1,area:sdk" --body @"
## Contexto
Instrumentación no intrusiva de los tres SDK. SPEC §3.1, §4.2 y §4.3.

## Criterios de aceptación
- [ ] OpenAI: ``responses.create`` y ``chat.completions.create``, sync/async, unary/stream
- [ ] Anthropic: ``messages.create`` y ``messages.stream``, sync/async
- [ ] Google: ``generate_content`` y ``generate_content_stream`` en cliente sync y ``aio``. Sin modo enterprise
- [ ] TTFT solo en stream, en el primer delta de texto de SPEC §4.3
- [ ] La excepción original se relanza después de emitir ``status=error``
- [ ] Tests con clientes falsos, sin red
"@
```

## Fase 2 — Proxy interceptor MCP

Depende de la Fase 1 porque el proxy emite eventos por el exporter de `multimcp`. Spec MCP: revisión 2026-07-28.

### M2.1 Proxy stdio

Labels: `milestone:m2`, `area:proxy`

Criterios de aceptación:

- `multimcp-proxy stdio --server-name NAME -- <comando>` lanza el subproceso.
- Cada línea JSON-RPC se reenvía sin cambiar `id`, `method`, `params` ni `result`.
- `stderr` del hijo se reenvía al stderr del proxy y no genera evento de error.
- Una línea que no es JSON genera `error_type=framing` y no se escribe en el otro extremo como si fuera un mensaje válido.

```powershell
gh issue create --title "M2.1 Proxy MCP stdio de la revisión 2026-07-28" --label "milestone:m2,area:proxy" --body @"
## Contexto
Interceptor transparente sobre stdin/stdout. SPEC §3.3 y §5.1.

## Criterios de aceptación
- [ ] CLI ``multimcp-proxy stdio --server-name NAME -- <comando>``
- [ ] Reenvío byte a byte lógico: id, method, params, _meta y result intactos
- [ ] stderr del hijo se reenvía y no cuenta como fallo de tool
- [ ] Línea inválida: evento ``error_type=framing`` y no se inyecta al otro extremo
- [ ] Test con un subproceso fixture, sin red
"@
```

### M2.2 Métricas de tools/call

Labels: `milestone:m2`, `area:proxy`

Criterios de aceptación:

- Cada request JSON-RPC con id produce un `McpEvent` de SPEC §5.2.
- `tools/call` llena `tool_name` desde `params.name`. Otros métodos dejan `tool_name` null.
- `payload_bytes` mide el `result` final, no los mensajes intermedios.
- Respuesta con `error` → `status=error`, `error_type=jsonrpc`, `error_code` copiado.
- Muerte del subproceso a mitad de request → `error_type=transport`.
- Las notificaciones se reenvían y no crean fila.

```powershell
gh issue create --title "M2.2 Métricas de tool, bytes y errores JSON-RPC" --label "milestone:m2,area:proxy" --body @"
## Contexto
Frecuencia, latencia, tamaño de contexto y tasa de fallos. SPEC §5.2 y §5.3.

## Criterios de aceptación
- [ ] Un evento por request con id. Las notificaciones no crean fila
- [ ] ``tools/call`` completa ``tool_name`` desde ``params.name``
- [ ] ``payload_bytes`` es el UTF-8 del result final
- [ ] Error JSON-RPC y muerte del subproceso cubiertos por la tabla de SPEC §5.3
- [ ] Los eventos salen por el exporter de multimcp, con test de MemoryExporter
"@
```

### M2.3 Proxy Streamable HTTP

Labels: `milestone:m2`, `area:proxy`

Criterios de aceptación:

- `multimcp-proxy http --listen HOST:PORT --upstream URL --server-name NAME`.
- Un POST del cliente se reenvía al upstream con headers y body intactos.
- Respuesta `application/json`: se mide y se devuelve igual.
- Respuesta `text/event-stream`: los frames SSE se retransmiten a medida que llegan. La latencia cierra en el frame que trae el result JSON-RPC.
- HTTP distinto de 200, o stream cortado antes del result: `error_type=transport`.

```powershell
gh issue create --title "M2.3 Proxy Streamable HTTP con respuestas SSE" --label "milestone:m2,area:proxy" --body @"
## Contexto
El binding HTTP vigente responde JSON o un SSE acotado al request. SPEC §3.3 y §5.

## Criterios de aceptación
- [ ] CLI ``multimcp-proxy http`` con listen y upstream
- [ ] POST reenviado sin modificar headers, _meta ni body
- [ ] Rama ``application/json`` y rama ``text/event-stream``
- [ ] La latencia del stream cierra en el result final; el progreso no suma bytes
- [ ] Test con un upstream ``httpx`` falso. El transporte 2024-11-05 de dos endpoints queda fuera
"@
```

## Fase 3 — Backend FastAPI, adaptadores de storage y evaluador RAG

### M3.1 App factory, settings y health

Labels: `milestone:m3`, `area:api`

Criterios de aceptación:

- `services/api` empaqueta `multimcp-api` e importa los modelos desde `multimcp`.
- Settings solo por entorno, según la tabla de SPEC §6.
- `GET /api/v1/health` y `?ready=true` con el contrato de SPEC §6.3.
- El sobre de error de SPEC §6.2. Un POST sin Bearer responde 401 cuando `INGEST_TOKEN` está seteado, y también 401 cuando está vacío.
- Test con `httpx.ASGITransport`.

```powershell
gh issue create --title "M3.1 App FastAPI, settings y sobre de error" --label "milestone:m3,area:api" --body @"
## Contexto
Esqueleto versionado /api/v1 antes de los repositorios. SPEC §6 y §6.2.

## Criterios de aceptación
- [ ] Paquete ``multimcp-api`` con settings de entorno y sin secretos por default
- [ ] Health y ready según SPEC §6.3
- [ ] Bearer obligatorio en POST. Token vacío también responde 401
- [ ] Sobre de error con schema_version, sin traceback
- [ ] Tests ASGI, sin base de datos
"@
```

### M3.2 PostgreSQL y Alembic

Labels: `milestone:m3`, `area:storage`

Criterios de aceptación:

- Migración `0001_init` con el SQL de SPEC §7, índices y checks.
- `PostgresEventRepository` implementa el `Protocol` de SPEC §6.4 para insert, finops, latency, trace y compare.
- `insert` es idempotente por `event_id`.
- Percentiles con `percentile_cont` 0.50 y 0.95.
- Hay un `MemoryEventRepository` que implementa el mismo `Protocol` para CI.
- Test de integración de Postgres marcado para correr solo si existe `DATABASE_URL`. CI default usa el repositorio en memoria.

```powershell
gh issue create --title "M3.2 Migración Alembic y repositorio PostgreSQL" --label "milestone:m3,area:storage" --body @"
## Contexto
Almacén portable por defecto. SPEC §6.4 y §7.

## Criterios de aceptación
- [ ] Alembic ``0001_init`` con las tres tablas, checks e índices
- [ ] ``PostgresEventRepository`` idempotente por ``event_id``
- [ ] p50 y p95 con ``percentile_cont``
- [ ] ``MemoryEventRepository`` para CI, mismo Protocol
- [ ] Test de Postgres se salta sin ``DATABASE_URL``
"@
```

### M3.3 Ingesta y consultas

Labels: `milestone:m3`, `area:api`

Criterios de aceptación:

- `POST /api/v1/events` y `POST /api/v1/mcp-events` con tope de 100 eventos y 1 MiB.
- `GET` de finops, latency, traces y compare con ventana máxima de 31 días.
- `include_judge=false` excluye `metadata.role=judge`.
- `group_by=mcp_server` no inventa costo de modelo.
- Validación de `schema_version` distinto de `1.0` responde 422.

```powershell
gh issue create --title "M3.3 Endpoints de ingesta, FinOps, latencia, trazas y compare" --label "milestone:m3,area:api" --body @"
## Contexto
Contratos HTTP de lectura y escritura. SPEC §6.3.

## Criterios de aceptación
- [ ] POST de eventos GenAI y MCP, idempotencia y límites de lote
- [ ] GET finops, latency, traces/{trace_id} y compare
- [ ] Ventana máxima de 31 días
- [ ] ``include_judge=false`` por defecto
- [ ] Tests del MemoryEventRepository cubren duplicados, 404 de traza y 422 de schema_version
"@
```

### M3.4 Adaptador BigQuery

Labels: `milestone:m3`, `area:storage`

Criterios de aceptación:

- `STORAGE_BACKEND=bigquery` construye `BigQueryEventRepository`. El módulo `google.cloud.bigquery` se importa ahí, no al arrancar en modo postgres.
- Tablas lógicas de SPEC §7.1. Percentiles con `APPROX_QUANTILES`.
- `insertId` = `event_id`.
- El evaluador no reclama jobs en BigQuery. Con ese backend, la documentación exige `EVAL_BACKEND=inline`.
- Test del adaptador con un cliente falso. Sin proyecto GCP en CI.

```powershell
gh issue create --title "M3.4 Adaptador BigQuery detrás de STORAGE_BACKEND" --label "milestone:m3,area:storage" --body @"
## Contexto
El mismo Protocol, activado por entorno. SPEC §3.7 y §7.1.

## Criterios de aceptación
- [ ] Import perezoso de google-cloud-bigquery
- [ ] Insert con insertId = event_id y percentiles por APPROX_QUANTILES
- [ ] El modo postgres no importa el cliente de GCP
- [ ] Documentar que la cola de evaluación no corre sobre BigQuery
- [ ] Test con cliente falso, sin credenciales
"@
```

### M3.5 Worker y juez RAG

Labels: `milestone:m3`, `area:eval`

Criterios de aceptación:

- `POST /api/v1/evaluations` responde 202 y persiste el job.
- El worker `python -m multimcp_api.eval.worker` reclama con `FOR UPDATE SKIP LOCKED`, lock con expiración y máximo 3 intentos.
- `EVAL_BACKEND=inline` usa `BackgroundTasks` y el mismo `JudgeClient`.
- Rúbrica `rag-judge-1.0` pide el JSON de SPEC §8. Salida validada con Pydantic. Un JSON inválido se reintenta una vez.
- El juez llama `responses.create` con `base_url=JUDGE_BASE_URL` a través de `wrap_openai`, con `metadata.role=judge`.
- Tests con un `JudgeClient` falso y con `httpx.MockTransport` en el SDK de OpenAI. Sin clave real.

```powershell
gh issue create --title "M3.5 Evaluador RAG desacoplado y juez OpenAI-compatible" --label "milestone:m3,area:eval" --body @"
## Contexto
LLM-as-a-Judge fuera del camino de la respuesta del usuario. SPEC §3.4 y §8.

## Criterios de aceptación
- [ ] POST 202 y GET del job
- [ ] Claim ``FOR UPDATE SKIP LOCKED``, expiración de lock y 3 intentos
- [ ] ``EVAL_BACKEND=inline`` con BackgroundTasks
- [ ] Rúbrica ``rag-judge-1.0`` y validación Pydantic de la salida
- [ ] La llamada del juez queda marcada ``metadata.role=judge``
- [ ] Tests sin red y sin JUDGE_API_KEY real
"@
```

### M3.6 Compose de API, worker y Postgres

Labels: `milestone:m3`, `area:infra`

Criterios de aceptación:

- `deploy/compose.yaml` levanta `postgres:16`, `api` y `worker` con la misma imagen y distinto comando.
- `INGEST_TOKEN` entra por entorno. El archivo de ejemplo no trae un secreto real.
- `GET /api/v1/health?ready=true` responde 200 cuando Postgres acepta conexiones.
- El README de la fase documenta el comando, sin ampliarse a un tutorial.

```powershell
gh issue create --title "M3.6 Compose de Postgres, API y worker" --label "milestone:m3,area:infra" --body @"
## Contexto
Camino portable sin GCP y sin Redis. SPEC §10.

## Criterios de aceptación
- [ ] compose con postgres:16, api y worker
- [ ] Token de ingesta solo por entorno
- [ ] Ready 200 contra Postgres
- [ ] No se agrega servicio Redis
"@
```

## Fase 4 — Dashboard React y Compose unificado

### M4.1 Scaffold del front

Labels: `milestone:m4`, `area:web`

Criterios de aceptación:

- `apps/web` creado con Vite, React 19 y TypeScript.
- `tsconfig` con `strict` y `noUncheckedIndexedAccess`.
- `"build": "tsc -b && vite build"`.
- Dependencias de SPEC §9: TanStack Query 5, React Router 7, Recharts 3, Tailwind CSS 4.
- `npm run build` pasa en CI.

```powershell
gh issue create --title "M4.1 Scaffold Vite, React 19 y TypeScript estricto" --label "milestone:m4,area:web" --body @"
## Contexto
Base del dashboard antes de las pantallas. SPEC §9.

## Criterios de aceptación
- [ ] Vite + React 19 + TypeScript con strict y noUncheckedIndexedAccess
- [ ] TanStack Query 5, React Router 7, Recharts 3 y Tailwind CSS 4
- [ ] ``npm run build`` ejecuta ``tsc -b && vite build``
- [ ] El workflow de CI deja de saltear el job web
"@
```

### M4.2 Cliente API, FinOps y latencia

Labels: `milestone:m4`, `area:web`

Criterios de aceptación:

- Cliente `fetch` tipado contra los JSON de SPEC §6.3. El token se lee de `sessionStorage`.
- Pantalla FinOps: gasto por modelo, por `prompt_version` y volumen por servidor MCP. Toggle `include_judge`.
- Pantalla Latencia: `p50`, `p95` y `error_rate`.
- Estados vacío, carga y error de red visibles. Un 401 muestra el campo del token.

```powershell
gh issue create --title "M4.2 Pantallas de FinOps y latencia" --label "milestone:m4,area:web" --body @"
## Contexto
Lectura de /api/v1/finops/summary y /api/v1/latency. SPEC §6.3 y §9.

## Criterios de aceptación
- [ ] Cliente fetch tipado. Token en sessionStorage, fuera del bundle
- [ ] FinOps por modelo, prompt_version y servidor MCP, con toggle del juez
- [ ] Latencia p50, p95 y error_rate
- [ ] Estados vacío, carga, error y 401
- [ ] Verificación manual en el navegador contra el compose de la Fase 3
"@
```

### M4.3 Trazas y comparador

Labels: `milestone:m4`, `area:web`

Criterios de aceptación:

- Inspector por `trace_id` con la línea de tiempo mezclada de eventos GenAI y MCP.
- Comparador de dos `prompt_version` o dos modelos, con el conteo de muestras en los dos lados.
- Un `trace_id` inexistente muestra el 404 del API, no una timeline vacía silenciosa.

```powershell
gh issue create --title "M4.3 Inspector de trazas y comparador de versiones" --label "milestone:m4,area:web" --body @"
## Contexto
GET /api/v1/traces/{trace_id} y GET /api/v1/compare. SPEC §6.3 y §9.

## Criterios de aceptación
- [ ] Timeline ordenada por occurred_at con spans de modelo y de tool
- [ ] Comparador lado a lado para prompt_version y para model
- [ ] El conteo de muestras queda visible
- [ ] Un 404 de traza se muestra como tal
"@
```

### M4.4 Compose unificado

Labels: `milestone:m4`, `area:infra`

Criterios de aceptación:

- `deploy/compose.yaml` suma el servicio `web` a Postgres, API y worker.
- El README raíz explica, en una página, cómo levantar el compose, envolver un cliente y apuntar el proxy stdio a un servidor MCP de ejemplo.
- `npm run build` del front y el health ready de la API son el criterio de "stack arriba".

```powershell
gh issue create --title "M4.4 Compose unificado y quickstart del README" --label "milestone:m4,area:infra" --body @"
## Contexto
Un comando levanta almacén, API, worker y dashboard. SPEC §10.

## Criterios de aceptación
- [ ] Servicio web en deploy/compose.yaml
- [ ] README con compose, ejemplo de wrap_openai y ejemplo de multimcp-proxy stdio
- [ ] El proxy sigue fuera del compose: corre al lado del servidor MCP del usuario
- [ ] Health ready y build del front verificados
"@
```

## Orden

```text
M1.1 → M1.2 → M1.3 → M1.4 → M1.5
                              ↓
                    M2.1 → M2.2 → M2.3
                              ↓
        M3.1 → M3.2 → M3.3 → M3.4
                      M3.2 → M3.5 → M3.6
                              ↓
              M4.1 → M4.2 → M4.3 → M4.4
```

M3.4 puede ir en paralelo con M3.5 después de M3.2. El resto es lineal: cada issue asume el contrato del anterior.
