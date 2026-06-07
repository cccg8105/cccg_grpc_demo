# Guía didáctica: entender RPC y gRPC con este ejemplo

Esta guía explica **qué es RPC**, **qué aporta gRPC** y **cómo funciona la demo** de este repositorio, pensando en alguien que nunca ha trabajado con comunicación entre servicios.

---

## 1. El problema que resuelve RPC

Imagina una aplicación dividida en varios programas que corren por separado (en contenedores, servidores distintos, etc.). Cada uno tiene una tarea concreta. Para colaborar, **tienen que hablarse**.

La forma más directa sería: “llama a esta función remota como si estuviera en tu mismo proceso”. Eso es la idea central de **RPC** (*Remote Procedure Call* — llamada a procedimiento remoto).

```mermaid
flowchart TB
  subgraph local [Programa A - Cliente]
    ClientCode["Tu codigo: stub.StartPipeline(...)"]
  end

  subgraph remoto [Programa B - Servidor]
    ServerCode["Codigo del servidor: StartPipeline()"]
  end

  ClientCode -->|"RPC: envia peticion"| Network[Red]
  Network --> ServerCode
  ServerCode -->|"RPC: devuelve respuesta"| Network
  Network --> ClientCode
```

En la práctica, el cliente **no llama una función Python/Go real del otro proceso**. En su lugar, usa un **stub** (código generado) que:

1. Empaqueta los datos en un mensaje estándar.
2. Los envía por la red al servidor.
3. Espera la respuesta y la convierte de nuevo en objetos de tu lenguaje.

Para ti, la experiencia se parece a llamar una función local.

---

## 2. RPC frente a una API REST habitual

Si ya conoces HTTP con JSON (REST), esta comparación ayuda:

| Aspecto | REST típico (HTTP + JSON) | gRPC (RPC moderno) |
|---------|----------------------------|---------------------|
| Contrato | Documentación OpenAPI, a veces informal | Archivo `.proto` estricto y versionable |
| Formato | Texto JSON (legible, más pesado) | Binario Protocol Buffers (compacto, rápido) |
| Modelo mental | Recursos (`GET /users/1`) | Procedimientos/servicios (`GetUser`, `StartPipeline`) |
| Streaming | Posible pero no es lo habitual | Tipos de stream nativos (cliente, servidor, bidireccional) |
| Uso típico | APIs públicas, navegadores | Comunicación **entre servicios** en backend |

```mermaid
flowchart LR
  subgraph rest [Enfoque REST]
    Browser1[Navegador] -->|"GET /jobs JSON"| ApiRest[API HTTP]
  end

  subgraph grpc [Enfoque gRPC]
    ServiceA[Servicio A] -->|"StartPipeline protobuf"| ServiceB[Servicio B]
  end
```

**Importante para esta demo:** el navegador **no habla gRPC directamente**. Por eso existe un **gateway** que traduce entre HTTP (familiar para el frontend) y gRPC (eficiente entre servicios backend).

---

## 3. Qué es gRPC en una frase

**gRPC** es un framework de RPC creado por Google que usa:

- **Protocol Buffers (protobuf)** para definir mensajes y servicios en archivos `.proto`.
- **HTTP/2** como transporte (multiplexación, eficiente).
- **Código generado** en muchos lenguajes (Python, Go, Java, etc.) a partir del `.proto`.

El contrato de nuestra demo está en [`proto/pipeline/v1/pipeline.proto`](../proto/pipeline/v1/pipeline.proto).

```mermaid
flowchart TB
  ProtoFile["pipeline.proto\n(contrato)"]
  ProtoFile --> Protoc[Compilador protoc]
  Protoc --> PyStubs[Stubs Python]
  Protoc --> OtherLang[Stubs otros lenguajes]

  PyStubs --> IngestSvc[Servicio Ingest]
  PyStubs --> TransformSvc[Servicio Transform]
  PyStubs --> GatewaySvc[Gateway]
```

El `.proto` es como un **contrato firmado** entre equipos: si cambias un campo, todos los servicios deben regenerar su código y adaptarse.

---

## 4. Los tres tipos de llamada gRPC (con analogías)

gRPC no solo envía “una petición → una respuesta”. También soporta **streams** (flujos continuos de mensajes).

### 4.1 Unary (una ida, una vuelta)

Como una pregunta concreta y una respuesta concreta.

> *“¿Puedes iniciar el pipeline con este archivo?” → “Sí, job_id = abc-123”*

En nuestra demo: `StartPipeline`.

### 4.2 Client streaming (el cliente envía muchos mensajes)

El cliente manda una secuencia; el servidor responde **una vez** al final.

> *Como entregar una caja con 50 000 fichas, una a una, y al terminar recibir el resumen total.*

En nuestra demo: `TransformStream` — **Ingest** envía miles de `RawRecord` y **Transform** devuelve un `TransformSummary`.

### 4.3 Server streaming (el servidor envía muchos mensajes)

Una petición inicial y luego el servidor va emitiendo resultados.

> *Como pedir “empezar a transmitir el partido” y recibir jugada tras jugada.*

En variantes de la demo se usaría así; aquí el progreso hacia la UI usa otro canal (SSE), pero el concepto es el mismo.

### 4.4 Resumen visual

```mermaid
flowchart TB
  subgraph unary [Unary]
    C1[Cliente] -->|"1 mensaje"| S1[Servidor]
    S1 -->|"1 respuesta"| C1
  end

  subgraph clientStream [Client streaming]
    C2[Cliente] -->|"mensaje 1"| S2[Servidor]
    C2 -->|"mensaje 2"| S2
    C2 -->|"mensaje N"| S2
    S2 -->|"1 respuesta final"| C2
  end

  subgraph serverStream [Server streaming]
    C3[Cliente] -->|"1 peticion"| S3[Servidor]
    S3 -->|"evento 1"| C3
    S3 -->|"evento 2"| C3
    S3 -->|"evento N"| C3
  end
```

---

## 5. La historia de nuestra demo

**Escenario:** procesar un archivo CSV enorme de transacciones bancarias (~50 000 filas) sin cargarlo entero en memoria ni bloquear la interfaz.

**Actores:**

| Componente | Rol en la historia |
|------------|-------------------|
| **Frontend (Svelte)** | Pantalla donde el usuario pulsa “Iniciar pipeline” y ve el progreso |
| **Gateway** | Puerta de entrada HTTP para el navegador; también servidor gRPC de progreso |
| **Ingest** | Lee el CSV por trozos (chunks) y los envía al siguiente servicio |
| **Transform** | Convierte monedas, clasifica comercios, marca transacciones de alto valor |
| **transactions.csv** | Archivo de datos de ejemplo montado en el contenedor |

```mermaid
flowchart LR
  User[Usuario] --> UI[Frontend Svelte]
  UI -->|"HTTP POST /jobs"| GW[Gateway]
  UI -->|"SSE eventos en vivo"| GW
  GW -->|"gRPC StartPipeline"| ING[Ingest]
  ING -->|"gRPC TransformStream"| TRF[Transform]
  ING --> CSV[(transactions.csv)]
  TRF -->|"gRPC PublishEvents"| GW
```

---

## 6. Paso a paso: qué ocurre al pulsar “Iniciar pipeline”

```mermaid
sequenceDiagram
  participant User as Usuario
  participant UI as Frontend
  participant GW as Gateway
  participant ING as Ingest
  participant TRF as Transform
  participant CSV as Archivo CSV

  User->>UI: Clic en Iniciar pipeline
  UI->>GW: POST /jobs
  GW->>ING: gRPC StartPipeline
  ING-->>GW: job_id + status started
  GW-->>UI: job_id

  UI->>GW: Abre SSE /jobs/id/events

  ING->>CSV: Lee filas por chunks
  loop Por cada fila o chunk
    ING->>TRF: RawRecord en TransformStream
    TRF->>TRF: Transforma registro
    TRF->>GW: ProgressEvent cada 50 filas
    GW-->>UI: Evento SSE
  end

  TRF-->>ING: TransformSummary final
  TRF->>GW: ProgressEvent job_complete
  GW-->>UI: Evento SSE final
```

### Paso 1 — El frontend pide un trabajo

El navegador hace `POST /jobs` con parámetros como:

- `chunk_size`: cuántas filas procesar antes de una pausa opcional (útil en modo demo).
- `sleep_ms`: retardo artificial para **ver** el streaming en pantalla.

El gateway genera un `job_id` único.

### Paso 2 — El gateway dispara Ingest (RPC unary)

```text
StartPipeline(job_id, file_path, chunk_size, sleep_ms)
         ↓
StartPipelineResponse(job_id, status="started")
```

Ingest arranca en segundo plano: no bloquea la respuesta HTTP.

### Paso 3 — Ingest streama registros a Transform (client streaming)

Por cada fila del CSV, Ingest crea un mensaje `RawRecord`:

```text
RawRecord {
  job_id,
  line_number,
  payload_json,      // fila del CSV en JSON
  bytes_read,        // acumulado JSON enviado por gRPC
  total_rows_estimate,
  total_file_bytes   // tamaño del CSV en disco
}
```

Los envía uno tras otro por `TransformStream`. **No espera a leer las 50 000 filas** para empezar a transformar: el pipeline fluye en pipeline real.

### Paso 4 — Transform enriquece y reporta progreso

Por cada registro, Transform:

1. Convierte la moneda a USD (tipos de cambio fijos en la demo).
2. Asigna categoría al comercio (retail, food, etc.).
3. Marca `high_value` si supera un umbral.

Cada 50 filas, envía un `ProgressEvent` al gateway vía `PublishEvents` (client streaming hacia el gateway). El evento incluye tanto **filas** (métrica de negocio) como **bytes** (métrica de transporte gRPC):

```text
ProgressEvent {
  rows_processed, rows_rejected, total_usd,
  bytes_streamed,              // JSON acumulado en tránsito
  total_file_bytes,            // tamaño del CSV en disco
  throughput_rows_per_sec,
  throughput_bytes_per_sec
}
```

### Dos formas de medir el progreso (filas vs bytes)

```mermaid
flowchart LR
  subgraph disco [Archivo en disco]
    CSV["transactions.csv\n~25 MB CSV"]
  end

  subgraph stream [Stream gRPC Ingest a Transform]
    JSON["Payload JSON por fila\nbytes_read acumulado"]
  end

  CSV -->|"total_file_bytes"| UI[Frontend]
  JSON -->|"bytes_streamed"| UI
```

| Métrica | Qué mide | Para qué sirve en la demo |
|---------|----------|---------------------------|
| **Filas** | Registros procesados / estimados | Progreso de negocio; barra principal en la UI |
| **Bytes en disco** | `stat()` del CSV | Contexto de “archivo grande” (~25 MB) |
| **Bytes en stream** | Suma del JSON enviado por gRPC | Ilustra volumen de datos **viajando entre contenedores** |

Los bytes en stream serán **menores** que el archivo en disco (no incluyen cabecera CSV ni formato original). Por eso la UI muestra ambos con etiquetas distintas, sin reemplazar la barra de progreso por filas.

### Paso 5 — El gateway traduce gRPC → SSE → UI

El navegador no entiende gRPC, pero sí **SSE** (*Server-Sent Events*): una conexión HTTP donde el servidor empuja eventos de texto.

El frontend actualiza:

- Barra de progreso (% por **filas**).
- Throughput (filas/s y KB/s o MB/s del stream gRPC).
- Contador de datos en stream vs tamaño del archivo en disco.
- Suma acumulada en USD.
- Feed con preview del último registro transformado.
- Diagrama animado `Ingest → Transform → Gateway/UI` (arista Ingest→Transform muestra bytes streamados).

---

## 7. Por qué hay un Gateway (idea clave)

```mermaid
flowchart TB
  subgraph browserZone [Zona del navegador]
    FE[Frontend]
  end

  subgraph backendZone [Zona backend - gRPC]
    GW[Gateway]
    ING[Ingest]
    TRF[Transform]
    ING <-->|gRPC| TRF
    TRF -->|gRPC| GW
    GW -->|gRPC| ING
  end

  FE -->|"HTTP + SSE\n(facil en browser)"| GW
```

| Capa | Protocolo | Motivo |
|------|-----------|--------|
| Frontend ↔ Gateway | HTTP, JSON, SSE | Estándar web, sin plugins |
| Gateway ↔ Ingest/Transform | gRPC + protobuf | Rápido, tipado, streaming nativo |

El gateway cumple dos roles:

1. **API REST** para iniciar jobs y consultar estado.
2. **Servidor gRPC `ProgressService`** para recibir eventos de Transform y reenviarlos al navegador.

---

## 8. Los servicios gRPC definidos en el contrato

```mermaid
classDiagram
  class IngestService {
    +StartPipeline(request) response
    +Ping(request) response
  }

  class TransformService {
    +TransformStream(stream RawRecord) TransformSummary
    +Ping(request) response
  }

  class ProgressService {
    +PublishEvents(stream ProgressEvent) Ack
    +Ping(request) response
  }

  note for IngestService "Unary: dispara el pipeline"
  note for TransformService "Client stream: recibe filas, devuelve resumen"
  note for ProgressService "Client stream: eventos de progreso hacia UI"
```

| Servicio | Método | Tipo RPC | Quién llama a quién |
|----------|--------|----------|---------------------|
| `IngestService` | `StartPipeline` | Unary | Gateway → Ingest |
| `TransformService` | `TransformStream` | Client streaming | Ingest → Transform |
| `ProgressService` | `PublishEvents` | Client streaming | Transform → Gateway |

Los métodos `Ping` existen para **healthchecks**: Docker verifica que cada contenedor responde antes de considerarlo listo.

---

## 9. Contenedores: un ecosistema aislado

Cada servicio corre en su propio contenedor, conectados por una red interna `grpc-net`.

```mermaid
flowchart TB
  subgraph host [Tu maquina]
    Port5173[":5173"]
    Port8080[":8080"]
  end

  subgraph compose [Docker Compose]
    FE[frontend]
    GW[gateway]
    ING[ingest-service]
    TRF[transform-service]
    DATA[(data/transactions.csv)]
  end

  Port5173 --> FE
  Port8080 --> GW
  FE --> GW
  GW --> ING
  ING --> TRF
  TRF --> GW
  ING --> DATA
```

Solo **frontend** y **gateway** exponen puertos al exterior. Ingest y Transform son **internos**: hablan gRPC entre ellos sin ser accesibles directamente desde tu navegador. Eso refuerza el modelo de microservicios.

Orden de arranque (simplificado):

1. Gateway (debe estar listo para recibir progreso).
2. Transform (depende del gateway).
3. Ingest (depende de transform).
4. Frontend (depende del gateway).

---

## 10. Qué transforma exactamente el servicio Transform

Ejemplo de fila de entrada (CSV):

```text
id,amount,currency,merchant,timestamp
TXN-000001,152.30,EUR,Amazon,2024-01-01T00:03:00
```

Después de transformar (conceptualmente):

```json
{
  "id": "TXN-000001",
  "amount_usd": 164.48,
  "category": "retail",
  "merchant": "Amazon",
  "high_value": false,
  "original_currency": "EUR",
  "original_amount": 152.30
}
```

```mermaid
flowchart LR
  Raw[Fila CSV cruda] --> Validate[Validar campos]
  Validate --> FX[Convertir a USD]
  FX --> Category[Clasificar merchant]
  Category --> Flag[Marcar high_value]
  Flag --> Out[Registro enriquecido]
```

La UI muestra estos resultados en el feed en tiempo real, no el CSV crudo.

---

## 11. Streaming vs procesar todo de golpe

Sin streaming (enfoque naive):

```mermaid
flowchart LR
  A[Leer 50k filas a memoria] --> B[Transformar todo] --> C[Responder al usuario]
```

Problemas: mucha memoria, latencia alta, el usuario no ve nada hasta el final.

Con streaming (nuestra demo):

```mermaid
flowchart LR
  R1[Leer fila 1] --> T1[Transformar 1] --> U1[Actualizar UI]
  R2[Leer fila 2] --> T2[Transformar 2] --> U2[Actualizar UI]
  RN[...] --> TN[...] --> UN[...]
```

Ventajas:

- **Menor pico de memoria** (procesas en chunks).
- **Feedback inmediato** (barra de progreso, filas/s).
- **Backpressure natural**: Transform consume a la velocidad que puede; Ingest puede pausar entre chunks.

El parámetro `sleep_ms` y el **modo lento** de la UI existen solo para hacer visible este flujo en una demo en vivo.

---

## 12. Glosario rápido

| Término | Significado sencillo |
|---------|---------------------|
| **RPC** | Llamar a una función que vive en otro programa, a través de la red |
| **gRPC** | Implementación moderna de RPC con protobuf y HTTP/2 |
| **Protobuf** | Formato binario + lenguaje para definir mensajes (`.proto`) |
| **Stub** | Código generado que “simula” la función remota en el cliente |
| **Servicer** | Implementación real del servicio en el servidor |
| **Unary** | Una petición, una respuesta |
| **Client streaming** | Cliente envía secuencia; servidor responde al cerrar |
| **Server streaming** | Cliente pide una vez; servidor envía secuencia |
| **SSE** | El servidor empuja eventos al navegador por HTTP |
| **Gateway** | Puente entre el mundo web (HTTP) y el mundo gRPC (backend) |
| **Pipeline** | Cadena de servicios donde la salida de uno alimenta al siguiente |

---

## 13. Cómo experimentar y qué observar

1. Levanta el entorno: `docker compose up --build`
2. Abre http://localhost:5173
3. Activa **modo lento** y pulsa **Iniciar pipeline**
4. Observa en paralelo:
   - El diagrama pulsando en `Ingest`, luego `Transform`, luego `Gateway/UI`
   - La barra de progreso avanzando
   - El feed con previews JSON cada pocos eventos
5. (Opcional) Mira los logs: `docker compose logs -f`

Preguntas guía para profundizar:

- ¿Qué pasaría si Transform se cae a mitad del stream?
- ¿Por qué no enviamos un evento SSE por cada fila (50 000 eventos)?
- ¿Qué ventaja tiene tener Ingest y Transform en procesos separados?

---

## 14. Mapa mental final

```mermaid
mindmap
  root((Demo gRPC))
    Problema
      Archivo grande
      Varios servicios
      UI en tiempo real
    Solucion RPC
      Contrato proto
      Stubs generados
      Llamadas tipadas
    Tipos de stream
      StartPipeline unary
      TransformStream client
      PublishEvents client
    Capas
      Browser HTTP SSE
      Backend gRPC
      Contenedores Docker
    Resultado
      Pipeline visible
      Metricas en vivo
      Aprendizaje practico
```

---

## 15. Siguientes pasos de aprendizaje

1. Abre [`proto/pipeline/v1/pipeline.proto`](../proto/pipeline/v1/pipeline.proto) y relaciona cada `rpc` con la secuencia del diagrama.
2. Lee [`services/ingest/server.py`](../services/ingest/server.py) — fíjate en el generador que alimenta `TransformStream`.
3. Lee [`services/transform/server.py`](../services/transform/server.py) — busca `_emit_progress`.
4. Lee [`services/gateway/main.py`](../services/gateway/main.py) — combina FastAPI, SSE y el servicer gRPC.
5. Modifica `PROGRESS_EVERY` o `chunk_size` y observa cómo cambia la experiencia en la UI.

---

## 16. Comparación REST vs gRPC (pestañas en la UI)

La demo incluye un **segundo stack** para contrastar el pipeline gRPC con el patrón tradicional de **APIs REST por lotes**, orquestado desde el browser con loops `fetch`.

### Arquitectura REST

```mermaid
flowchart LR
  UI[Frontend tab REST]
  RING[rest-ingest:8091]
  RTRF[rest-transform:8092]
  CSV[(transactions.csv)]

  UI -->|"GET /meta"| RING
  UI -->|"loop GET /records"| RING
  UI -->|"loop POST /transform"| RTRF
  RING --> CSV
```

### Secuencia típica (REST)

```mermaid
sequenceDiagram
  participant UI as Browser
  participant ING as rest_ingest
  participant TRF as rest_transform

  UI->>ING: GET /meta
  loop Por cada lote
    UI->>ING: GET /records offset limit
    UI->>TRF: POST /transform
    UI->>UI: actualizar metricas
  end
```

### Trade-offs esperados en la demo

| Aspecto | Pipeline gRPC | REST por lotes |
|---------|---------------|----------------|
| Peticiones desde el browser | ~2 (POST + SSE) | `1 + 2 × lotes` |
| Orquestación | Backend (Ingest → Transform) | Frontend (loop) |
| Progreso | Push SSE | Pull tras cada lote |
| Contrato | `.proto` tipado | JSON OpenAPI-style |
| Bytes al browser | Eventos SSE compactos | Respuestas JSON completas por lote |

### Cómo usar la comparativa

1. Abre http://localhost:5173
2. Configura **chunk size** y **modo lento** (compartidos entre pestañas)
3. Ejecuta **Pipeline gRPC** → se guardan métricas
4. Cambia a **API REST por lotes** → ejecuta de nuevo
5. Revisa la **tabla comparativa** (tiempo, peticiones, bytes, filas)

Interpretación didáctica: REST suele mostrar **más peticiones HTTP** y **más bytes JSON** recibidos en el browser; gRPC suele mostrar **menos round-trips** desde el cliente y progreso continuo vía SSE mientras el pipeline corre en backend.

---

## Referencias en este repositorio

| Recurso | Contenido |
|---------|-----------|
| [`README.md`](../README.md) | Comandos para ejecutar la demo |
| [`proto/pipeline/v1/pipeline.proto`](../proto/pipeline/v1/pipeline.proto) | Contrato gRPC |
| [`docker-compose.yml`](../docker-compose.yml) | Topología de contenedores |
| [`frontend/src/App.svelte`](../frontend/src/App.svelte) | UI con pestañas gRPC/REST y comparativa |
| [`services/rest_ingest/main.py`](../services/rest_ingest/main.py) | API REST paginada |
| [`services/rest_transform/main.py`](../services/rest_transform/main.py) | API REST de transformación |

---

*Documento generado para acompañar la demo `rpc_demo`. Si compartes esta guía en una charla, recomendamos proyectar el diagrama de secuencia (sección 6) mientras ejecutas la demo en vivo.*

**Documentación técnica (mantenimiento):** [DESCRIPCION_TECNICA.md](DESCRIPCION_TECNICA.md)
