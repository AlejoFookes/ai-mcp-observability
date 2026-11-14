# @multimcp/web

Dashboard Vite + React 19 + TypeScript for multiMCP FinOps, latency, traces and compare.

```bash
cd apps/web
npm install
npm run dev
npm run build
```

- Token: `sessionStorage` via the shell form (never bundled).
- Dev proxy: `/api` → `http://127.0.0.1:8000`.
- Contracts: hand-typed in `src/api/types.ts` against SPEC §6.3.
