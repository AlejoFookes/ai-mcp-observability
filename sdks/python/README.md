# multimcp

SDK Python de la plataforma multiMCP. Envuelve clientes `openai`, `anthropic` y `google-genai` y emite un evento por llamada con tokens, TTFT, latencia, costo estimado y errores. Nunca envía el texto del prompt ni de la respuesta.

```bash
uv add "multimcp[openai]"
```

El contrato del evento y las reglas de precio están en [`SPEC.md`](../../SPEC.md), sección 4.
