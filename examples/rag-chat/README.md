# Acme Shop — RAG chat (demo multiMCP)

Chat de soporte con RAG sobre políticas locales (`data/*.md`). Cada respuesta pasa por
`wrap_openai` + `prompt_context`, así el dashboard multiMCP ve **costo, latencia y trazas**.

## Qué demuestra

| Acción en el chat | Qué mirás en el dashboard |
| --- | --- |
| Varias preguntas | **FinOps** por `openai/<modelo>` |
| Alternar `support-v1` / `support-v2` | **Compare** → dimension `prompt_version` |
| Copiar `trace_id` de una respuesta | **Traces** |
| Muchas preguntas | **Latency** p50/p95 |

## Requisitos

1. API multiMCP en `http://127.0.0.1:8000` (p. ej. `STORAGE_BACKEND=memory` o Compose).
2. Dashboard: `cd apps/web && npm run dev` → http://127.0.0.1:5173 (token = `INGEST_TOKEN`).
3. Key en el **`.env` de la raíz del repo** (la misma que el Playground). Con Groq:
   `OPENAI_API_KEY=gsk_…`, `OPENAI_BASE_URL=https://api.groq.com/openai/v1`.
   El chat usa retrieval **lexical** con Groq (no necesita embeddings de OpenAI).

## Arranque

```powershell
cd examples\rag-chat
# No hace falta copiar .env si ya está en la raíz del repo.

$uv = "$env:USERPROFILE\.local\bin\uv.exe"
& $uv sync
& $uv run streamlit run app.py
```

Abrí la URL que imprime Streamlit (suele ser http://127.0.0.1:8501).

## Flujo recomendado (15 min)

1. Hacé 3 preguntas con **support-v1**.
2. Cambiá a **support-v2** y repetí preguntas parecidas.
3. Dashboard → FinOps: gasto por modelo y por `prompt_version`.
4. Compare: Left `support-v1`, Right `support-v2` (mirá el conteo de muestras).
5. Traces: pegá un `trace_id` de la caption de una respuesta.

## Notas

- Los embeddings **no** pasan por el wrapper GenAI de 0.1 (solo chat/responses); el costo
  visible en FinOps es el de las completions del chat.
- Es un side demo, no un producto: sin auth de usuarios, sin vector DB, corpus en RAM.
