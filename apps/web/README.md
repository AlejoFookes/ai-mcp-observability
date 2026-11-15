# @multimcp/web

Dashboard Vite + React 19 + TypeScript for multiMCP FinOps, latency, traces and compare.

## M4.2 screens

- **FinOps** (`/`): `GET /api/v1/finops/summary` by model, `prompt_version` and MCP server volume, with date window and `include_judge`.
- **Latency** (`/latency`): `GET /api/v1/latency` for p50 / p95 / error_rate by model, operation or MCP tool.
- **Traces** (`/traces`): live list via `GET /api/v1/traces` (newest first) + detail `GET /api/v1/traces/{trace_id}`.
- **Compare** (`/compare`): `GET /api/v1/compare` side-by-side for `prompt_version` or `model`, with sample counts.
- **Playground** (`/playground`): `POST /api/v1/playground/dual` — same prompt on two models; telemetry feeds FinOps/Traces.

Save the ingest Bearer token in the shell (sessionStorage). Dev proxy: `/api` → `http://127.0.0.1:8000`.
API playground defaults to **Groq** (`OPENAI_BASE_URL=https://api.groq.com/openai/v1`).
Set `OPENAI_API_KEY` to a Groq key from https://console.groq.com/keys (OpenAI-compatible client).

```bash
cd apps/web
npm install
npm run dev
npm run build
```

- Token: `sessionStorage` via the shell form (never bundled).
- Dev proxy: `/api` → `http://127.0.0.1:8000`.
- Contracts: hand-typed in `src/api/types.ts` against SPEC §6.3.
