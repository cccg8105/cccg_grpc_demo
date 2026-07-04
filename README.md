# gRPC Pipeline Demo

Demo didáctica que **compara** un pipeline gRPC con un pipeline REST **equiparable** (mismo `POST /jobs` + SSE en el navegador, misma semántica de `chunk_size`), usando el mismo CSV y la misma lógica de transformación.

> **Guía para principiantes:** [docs/GUIA_DIDACTICA.md](docs/GUIA_DIDACTICA.md) — explicación didáctica de RPC/gRPC con diagramas Mermaid.  
> **Documentación técnica:** [docs/DESCRIPCION_TECNICA.md](docs/DESCRIPCION_TECNICA.md) — estructura del proyecto, flujos y guía de mantenimiento para desarrolladores.  
> **Presentación:** [presentation/README.md](presentation/README.md) — *Cuando los datos deben fluir entre servicios* (Quarto + reveal.js, autor: César Cárdenas).

## Arquitectura

```mermaid
flowchart LR
  UI[SvelteFrontend] -->|POST /jobs| GW[Gateway:8080]
  UI -->|SSE /jobs/id/events| GW
  GW -->|RunPipeline stream| ING[Ingest:50051]
  ING -->|TransformStream bidi| TRF[Transform:50052]
  ING --> DATA[(transactions.csv)]

  UI2[RestTab] -->|POST /jobs| RGW[rest-gateway:8090]
  UI2 -->|SSE| RGW
  RGW --> RING[rest-ingest:8091]
  RING -->|POST /transform| RTRF[rest-transform:8092]
  RING -->|POST /internal/progress| RGW
  RING --> DATA
```

## Requisitos

- Docker y Docker Compose
- Python 3.11+ (solo para generar proto/CSV en local)

## Inicio rápido

```bash
# Generar stubs gRPC y CSV de ejemplo (local)
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python scripts/generate_proto.py
.venv/Scripts/python scripts/generate_sample_csv.py --rows 50000

# Levantar todo el ecosistema
docker compose up --build
```

Abre **http://localhost:5173**:

1. Pestaña **Pipeline gRPC** — diagrama hub gateway, SSE en vivo
2. Pestaña **Pipeline REST** — mismo patrón browser (`POST` + SSE); HTTP interno entre servicios
3. **Tabla comparativa** — tras ejecutar ambos modos, compara tiempo, peticiones y bytes

Observa en gRPC:

- Barra de progreso por **filas** y métricas de **bytes en stream gRPC**
- Throughput dual: filas/s y KB/s
- Feed SSE con previews de registros transformados

## Servicios

| Servicio | Puerto | Rol |
|----------|--------|-----|
| `frontend` | 5173 | UI Svelte |
| `gateway` | 8080 | REST + SSE; cliente gRPC de `RunPipeline` |
| `ingest-service` | 50051 | Orquesta CSV, transform y stream de progreso |
| `transform-service` | 50052 | Worker: transforma lotes (bidi gRPC) |
| `rest-gateway` | 8090 | REST + SSE (browser) |
| `rest-ingest` | 8091 | Orquesta pipeline REST; publica progreso al gateway |
| `rest-transform` | 8092 | Worker: `POST /transform` por lote |

## API rest-gateway (modo REST)

Mismo contrato HTTP que el gateway gRPC (puerto **8090**):

- `POST /jobs` — body: `{ "file_path", "chunk_size", "sleep_ms" }`
- `GET /jobs/{id}/events` — SSE de eventos de progreso
- `GET /health` — healthcheck HTTP

Endpoints internos (`rest-ingest`, `rest-transform`) no los usa el browser. Ver [docs/FLUJO_REST_GATEWAY_SSE.md](docs/FLUJO_REST_GATEWAY_SSE.md).

## API del gateway (modo gRPC)

- `POST /jobs` — body: `{ "file_path", "chunk_size", "sleep_ms" }`
- `GET /jobs/{id}/events` — SSE de eventos de progreso
- `GET /health` — healthcheck HTTP

## Desarrollo local

Frontend sin Docker:

```bash
cd frontend
npm install
VITE_GATEWAY_URL=http://localhost:8080 \
VITE_REST_GATEWAY_URL=http://localhost:8090 \
npm run dev
```

Smoke tests locales:

```bash
.venv/Scripts/python scripts/smoke_test.py
.venv/Scripts/python scripts/smoke_test_rest.py
```

Regenerar proto tras cambios en `proto/`:

```bash
.venv/Scripts/python scripts/generate_proto.py
```

## Presentación

Slides didácticas sobre gRPC, cuándo usarlo y la demo interactiva. Requiere [Quarto](https://quarto.org/docs/get-started/).

Ver [presentation/README.md](presentation/README.md). Render:

```bash
quarto render presentation/grpc-intro.qmd
python scripts/patch_presentation_html.py
# o
make presentation
```

Verificación visual automatizada (Playwright):

```bash
make presentation-verify
```

## Notas

- El navegador no usa gRPC directamente; el gateway traduce eventos gRPC a SSE.
- `sleep_ms` y **modo lento** en la UI hacen visible el streaming (~2–5 s).
- El CSV demo tiene ~50k filas en `data/transactions.csv`.
- **Bytes en stream** (`bytes_streamed`) mide payload lógico JSON acumulado por fila; **bytes wire** en gRPC usa `TransactionRecord` tipado (menor que REST JSON). **Bytes en disco** (`total_file_bytes`) es el tamaño del CSV.
