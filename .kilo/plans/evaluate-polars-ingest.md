# Plan: Evaluar migración de lectura CSV en ingest a Polars

## Objetivo
Evaluar si es viable y conveniente reemplazar la lectura de CSV en `services/ingest/server.py` usando Polars para procesar en secciones/chunks sin cargar el archivo completo en memoria como DataFrame.

## Contexto actual
El código actual en `services/ingest/server.py` ya usa `csv.DictReader` dentro de un generador Python:
- **Ya es streaming**: lee fila por fila, no carga todo el CSV en memoria.
- `file_meta()` (en `common/csv_batch.py`) sí escanea el archivo para contar filas, pero es una operación ligera.
- Cada fila se serializa a JSON y se emite por gRPC.

## Análisis de viabilidad

### Ventajas potenciales de Polars
- `pl.read_csv_batched(path, batch_size=N)` permite leer el CSV en lotes de DataFrames pequeños.
- Motor Rust: parseo CSV potencialmente más rápido que `csv` estándar.
- Interfaz consistente si en el futuro se quiere usar Polars en otros servicios.

### Desventajas y riesgos
1. **Dependencia pesada**: Polars agrega ~100 MB de wheels compilados. Aumenta tamaño de imagen Docker y tiempo de build.
2. **Cambio de tipos**: Polars infiere tipos numéricos automáticamente. Si `amount` se lee como `Float64`, `json.dumps` producirá `123.4` en vez de `"123.4"`. `transform_record` espera strings para `float(payload["amount"])`, que funcionaría igual, pero el JSON emitido cambiaría levemente.
3. **Complejidad innecesaria**: El generador actual ya es O(1) en memoria. Polars no ofrece una ventaja decisiva aquí porque el cuello de botella real es la serialización JSON + latencia gRPC por fila.
4. **Falta en el proyecto**: No hay referencias a Polars en `requirements.txt`, Dockerfiles ni docs. Habría que agregarlo en 5 Dockerfiles.

### Conclusión preliminar
**No recomendado** para este caso de uso específico porque:
- La lectura ya es row-by-row con `csv.DictReader` (sin DataFrame en memoria).
- El overhead de agregar Polars supera el beneficio.
- Introduce riesgo de cambios sutiles en tipos de datos.

## Opciones a evaluar en plan

### Opción A: Mantener csv.DictReader (recomendada)
- **Cambios**: Ninguno. Documentar en código que la lectura ya es streaming.
- **Impacto**: Mantener simplicidad, sin nuevas dependencias.

### Opción B: Migrar a Polars con `read_csv_batched`
- **Cambios**:
  1. Agregar `polars` a `requirements.txt`.
  2. Actualizar `services/**/Dockerfile` para que incluyan Polars (todos usan el mismo `requirements.txt`).
  3. Modificar `record_generator` en `ingest/server.py` para usar `pl.read_csv_batched(path, batch_size=chunk_size)`.
  4. Convertir cada batch a diccionarios (`batch.to_dicts()` o `iter_rows(named=True)`).
  5. Asegurar que `transform_record` y `preview_record` manejen correctamente los tipos inferidos por Polars.
- **Riesgos**:
  - Cada batch DataFrame se carga en memoria, pero con `batch_size=chunk_size` (default 100) es trivial.
  - `file_meta()` sigue escaneando el archivo para contar filas; Polars no evitaría ese costo a menos que se replantee.
  - Posible breaking change en formato JSON emitido.

### Opción C: Híbrido — Polars solo para `file_meta` y `read_batch` en REST
- **Cambios**: Usar Polars en `csv_batch.py` para metadata y paginación.
- **Impacto**: Mejora performance en REST (reduce re-escaneo), pero no afecta el ingest gRPC.

## Preguntas para el usuario
1. ¿El objetivo es performance, claridad de código o aprender Polars en el proyecto?
2. ¿Estás dispuesto a agregar la dependencia de Polars y actualizar todos los Dockerfiles?
3. ¿Prefieres que implementemos la Opción B como plan detallado, o descartamos Polars y documentamos que la lectura actual ya es streaming?
