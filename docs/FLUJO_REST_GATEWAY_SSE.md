# Flujo del rest-gateway: REST, SSE y pipeline interno

Este documento describe el stack REST **equiparable** al gateway gRPC: mismo contrato HTTP hacia el navegador (`POST /jobs` + SSE), mismos roles de orquestación (Ingest orquesta, Gateway notifica).

## Qué representa el flujo

| Canal | Participantes | Rol |
|-------|---------------|-----|
| **HTTP** (REST + SSE) | Navegador ↔ rest-gateway | Lo que ve y usa el frontend |
| **HTTP interno** | rest-ingest ↔ rest-transform; rest-ingest → rest-gateway | Comunicación entre servicios backend |

El navegador **no** llama a `rest-ingest` ni `rest-transform` en el flujo principal.

## Paso 1 — El frontend inicia el job (una sola POST)

`RestTab.svelte` usa el mismo patrón que gRPC:

```
POST http://localhost:8090/jobs
Body: { file_path, chunk_size, sleep_ms }
```

**Respuesta:** `{ job_id, status }`

En `services/rest_gateway/routes/jobs.py`:

1. `hub.create_job()` genera un `job_id`.
2. Arranca un thread con `ingest_client.start_pipeline(job_id, ...)`.
3. Devuelve el `job_id` al navegador.

## Paso 2 — El frontend abre SSE

```
GET /jobs/{job_id}/events
```

`EventSource` en `api.ts` con `gatewayUrl: REST_GATEWAY_URL`. Mismo shape JSON de eventos que el gateway gRPC.

## Paso 3 — rest-gateway arranca el pipeline en rest-ingest

El thread del POST llama:

```
POST http://rest-ingest:8091/internal/start-pipeline
Body: { job_id, file_path, chunk_size, sleep_ms }
```

`rest_ingest` arranca `_run_pipeline` en background: lectura **secuencial** del CSV con `iter_csv_batches`.

## Paso 4 — rest-ingest orquesta transform y progreso

Por cada lote de `chunk_size` filas:

```
POST http://rest-transform:8092/transform
Body: { "records": [...] }
```

Tras recibir la respuesta del lote, **rest-ingest** publica progreso al gateway:

```
POST http://rest-gateway:8090/internal/progress
Body: ProgressPayload (alineado a ProgressEvent SSE)
```

`rest-transform` es un **worker puro**: solo transforma y responde JSON; no conoce al gateway.

## Paso 5 — SSE entrega el evento al navegador

Un evento SSE por lote completado (más `connected` y `job_complete`). `RestTab` actualiza métricas y diagrama igual que `GrpcTab`.

## Endpoints HTTP del rest-gateway

| Método | Ruta | Tipo | Uso |
|--------|------|------|-----|
| `POST` | `/jobs` | REST | Crear job y arrancar pipeline |
| `GET` | `/jobs/{job_id}` | REST | Snapshot (smoke test) |
| `GET` | `/jobs/{job_id}/events` | **SSE** | Stream en vivo |
| `POST` | `/internal/progress` | REST interno | Progreso desde rest-ingest |

## Archivos clave

| Archivo | Responsabilidad |
|---------|-----------------|
| `services/rest_gateway/routes/jobs.py` | POST, GET snapshot, GET SSE |
| `services/rest_gateway/routes/progress.py` | POST progreso interno |
| `services/rest_gateway/hub.py` | Jobs y fan-out SSE |
| `services/rest_gateway/ingest_client.py` | HTTP hacia rest-ingest |
| `services/rest_ingest/main.py` | Orquestador: CSV + transform + progreso |
| `services/rest_transform/main.py` | Worker: POST /transform |
| `services/common/progress_builder.py` | Construcción compartida de eventos |
| `frontend/src/lib/api.ts` | `startJob` / `subscribeToJob` parametrizados |

## Lectura relacionada

- [FLUJO_GATEWAY_SSE.md](FLUJO_GATEWAY_SSE.md) — stack gRPC equivalente.
- [GUIA_DIDACTICA.md](GUIA_DIDACTICA.md) — comparativa didáctica.
- [DESCRIPCION_TECNICA.md](DESCRIPCION_TECNICA.md) — detalle técnico.
