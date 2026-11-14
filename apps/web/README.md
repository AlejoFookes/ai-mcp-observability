# @multimcp/web

Dashboard Vite + React 19 + TypeScript for multiMCP FinOps, latency, traces and compare.

## M4.2 screens

- **FinOps** (`/`): `GET /api/v1/finops/summary` by model, `prompt_version` and MCP server volume, with date window and `include_judge`.
- **Latency** (`/latency`): `GET /api/v1/latency` for p50 / p95 / error_rate by model, operation or MCP tool.

Save the ingest Bearer token in the shell (sessionStorage). Dev proxy: `/api` → `http://127.0.0.1:8000`.

```bash
cd apps/web
npm install
npm run dev
npm run build
```

- Token: `sessionStorage` via the shell form (never bundled).
- Dev proxy: `/api` → `http://127.0.0.1:8000`.
- Contracts: hand-typed in `src/api/types.ts` against SPEC §6.3.
