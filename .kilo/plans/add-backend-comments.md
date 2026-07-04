# Plan: Add explanatory comments to backend services

## Goal
Add clear, descriptive comments to all Python backend service files to help understand their architecture, data flow, and logic.

## Files to modify

### 1. `gateway/main.py`
- Add comments at file level describing the gateway's dual role: REST API + gRPC ProgressService
- `JobState`: explain job lifecycle and subscriber pattern
- `JobHub`: describe in-memory registry, subscribers list, last_event caching
- `_event_to_dict`: note translation from protobuf to JSON for SSE
- `ProgressServicer`: explain it receives progress events from transform via gRPC client streaming
- `_start_pipeline`: note it runs in a background thread to avoid blocking HTTP response
- `create_job`: explain it creates a job, spawns pipeline thread, returns immediately
- `job_events`: describe SSE endpoint that yields 'connected' event then streams queue messages

### 2. `ingest/server.py`
- `record_generator`: explain how it opens CSV, iterates rows, serializes to JSON, tracks cumulative bytes, yields RawRecord proto, and applies chunk sleeps
- `_run_pipeline`: describe thread target that opens gRPC channel to transform, streams records via `TransformStream`, and logs summary
- Add comments about why thread is used (non-blocking StartPipeline)

### 3. `transform/server.py`
- `TransformStream`: explain the core client-streaming RPC: iterates incoming RawRecords, calls `transform_record`, maintains counters, emits progress events at intervals, and returns TransformSummary
- `_build_progress_event`: note fields populated for each progress emission
- `_emit_progress`: note it opens a new gRPC channel to gateway for each progress event (simple but not optimal)
- Add flow comments: first event ("ingest" stage), periodic updates ("transform" stage), final event ("complete" stage)

### 4. `rest_ingest/main.py`
- `get_meta`: returns CSV metadata (rows, bytes)
- `get_records`: paginated CSV access using offset/limit, computes has_more, includes response_bytes for metrics

### 5. `rest_transform/main.py`
- `transform_batch`: batch processor that loops over records, applies shared `transform_record`, aggregates totals, returns preview

### 6. `common/pipeline_utils.py`
- Existing docstrings are good; add more detail about EXCHANGE_RATES and MERCHANT_CATEGORIES
- `transform_record`: explicitly note it returns (result, error) tuple pattern

### 7. `common/csv_batch.py`
- `read_batch`: note it scans CSV from start to offset, not efficient for large offsets (acceptable for demo)
- `file_meta`: docstring for return dictionary keys

## Approach
- Add clear, non-redundant comments directly to each file
- Use inline comments for key logic and block comments for functions/classes
- Keep comments in Spanish to match the project's didactic style
- Maintain consistent formatting and Python 3.11+ style

## Impact
- Improves developer experience for understanding the codebase
- Bridges the gap between architecture docs (DESCRIPCION_TECNICA.md) and implementation
- Does not change any runtime behavior (comments only)
