## Qué cambia

<!-- Una o dos oraciones sobre el porqué. -->

## Milestone

Fase:

Issue:

## Spec

Sección de `SPEC.md` que implementa este PR:

## Cómo se probó

- [ ] `ruff check` en los paquetes Python tocados
- [ ] `pytest` sin red hacia OpenAI, Anthropic, Google o BigQuery
- [ ] `npm run build` si el PR toca `apps/web`
- [ ] El diff no incluye `.env`, claves ni connection strings

## Riesgos

<!-- Migraciones, contratos `schema_version`, catálogo de precios, compatibilidad del proxy MCP. -->

## Checklist

- [ ] El comportamiento coincide con `SPEC.md`. Si el spec quedó corto, este PR lo actualiza en el mismo cambio.
- [ ] Los wrappers siguen relanzando la excepción original del SDK.
- [ ] Un fallo de telemetría no cambia la respuesta del modelo ni el mensaje JSON-RPC.
- [ ] PostgreSQL sigue siendo el camino que levanta `deploy/compose.yaml` sin credenciales de GCP.
