<script lang="ts">
  import PipelineDiagram from '../PipelineDiagram.svelte';
  import {
    formatBytes,
    formatBytesPerSec,
    formatTime,
    progressPercent,
    startJob,
    subscribeToJob,
    type ProgressEvent,
  } from '../api';
  import {
    createEmptyRunMetrics,
    finalizeRunMetrics,
    type RunMetrics,
  } from '../runMetrics';

  type Props = {
    chunkSize: number;
    slowMode: boolean;
    onComplete: (metrics: RunMetrics) => void;
  };

  let { chunkSize, slowMode, onComplete }: Props = $props();

  export type FeedEntry = {
    time: string;
    stage: string;
    message: string;
    preview: string;
  };

  let running = $state(false);
  let jobId = $state('');
  let status = $state('idle');
  let activeStage = $state('');
  let rowsProcessed = $state(0);
  let rowsRejected = $state(0);
  let totalUsd = $state(0);
  let totalEstimate = $state(0);
  let throughput = $state(0);
  let bytesStreamed = $state(0);
  let totalFileBytes = $state(0);
  let bytesThroughput = $state(0);
  let requestCount = $state(0);
  let bytesTransferred = $state(0);
  let errorMessage = $state('');
  let feed = $state.raw<FeedEntry[]>([]);

  let unsubscribe: (() => void) | null = null;
  let startMs = 0;
  let firstUpdateMs: number | null = null;
  let percent = $derived(progressPercent(rowsProcessed + rowsRejected, totalEstimate));

  function resetMetrics() {
    rowsProcessed = 0;
    rowsRejected = 0;
    totalUsd = 0;
    totalEstimate = 0;
    throughput = 0;
    bytesStreamed = 0;
    totalFileBytes = 0;
    bytesThroughput = 0;
    requestCount = 0;
    bytesTransferred = 0;
    activeStage = '';
    feed = [];
    errorMessage = '';
    firstUpdateMs = null;
  }

  function handleEvent(event: ProgressEvent) {
    const payloadBytes = new TextEncoder().encode(JSON.stringify(event)).length;
    bytesTransferred += payloadBytes;

    if (event.type === 'connected') {
      status = 'connected';
      requestCount += 1;
      return;
    }

    if (firstUpdateMs === null) {
      firstUpdateMs = performance.now();
    }

    if (event.stage) {
      activeStage = event.stage === 'complete' ? 'ui' : event.stage;
    }
    if (event.rows_processed !== undefined) rowsProcessed = event.rows_processed;
    if (event.rows_rejected !== undefined) rowsRejected = event.rows_rejected;
    if (event.total_usd !== undefined) totalUsd = event.total_usd;
    if (event.total_rows_estimate !== undefined) totalEstimate = event.total_rows_estimate;
    if (event.throughput_rows_per_sec !== undefined) throughput = event.throughput_rows_per_sec;
    if (event.bytes_streamed !== undefined) bytesStreamed = event.bytes_streamed;
    if (event.total_file_bytes !== undefined) totalFileBytes = event.total_file_bytes;
    if (event.throughput_bytes_per_sec !== undefined) bytesThroughput = event.throughput_bytes_per_sec;

    feed = [
      {
        time: formatTime(event.timestamp_ms),
        stage: event.stage ?? 'unknown',
        message: event.message ?? '',
        preview: event.record_preview ?? '',
      },
      ...feed,
    ].slice(0, 80);

    if (event.job_complete) {
      status = 'complete';
      running = false;
      unsubscribe?.();
      unsubscribe = null;

      const base = createEmptyRunMetrics('grpc', chunkSize, slowMode);
      base.totalRows = totalEstimate;
      base.rowsProcessed = rowsProcessed;
      base.rowsRejected = rowsRejected;
      base.totalUsd = totalUsd;
      base.requestCount = requestCount;
      base.bytesTransferred = bytesTransferred;
      onComplete(finalizeRunMetrics(base, startMs, firstUpdateMs));
    } else {
      status = 'running';
    }
  }

  async function onStart() {
    if (running) return;

    resetMetrics();
    running = true;
    status = 'starting';
    startMs = performance.now();

    try {
      const sleepMs = slowMode ? 80 : 0;
      const result = await startJob({ chunkSize, sleepMs });
      requestCount = 1;
      jobId = result.job_id;
      status = 'streaming';

      unsubscribe = subscribeToJob(
        jobId,
        handleEvent,
        (error) => {
          errorMessage = error.message;
          running = false;
          status = 'error';
        },
      );
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Unknown error';
      running = false;
      status = 'error';
    }
  }
</script>

<section class="card controls">
  <div class="control-row">
    <button onclick={onStart} disabled={running}>Iniciar pipeline gRPC</button>
  </div>
  <div class="meta">
    <span>Estado: <strong>{status}</strong></span>
    {#if jobId}<span>Job: <code>{jobId}</code></span>{/if}
    {#if errorMessage}<span class="error">{errorMessage}</span>{/if}
  </div>
</section>

<PipelineDiagram
  {activeStage}
  {rowsProcessed}
  {throughput}
  {bytesStreamed}
  {bytesThroughput}
/>

<section class="grid grid-2">
  <article class="card metrics">
    <h2>Métricas gRPC</h2>
    <div class="progress-wrap">
      <div class="progress-bar grpc" style={`width: ${percent}%`}></div>
    </div>
    <p>{percent}% — {rowsProcessed.toLocaleString()} OK / {rowsRejected.toLocaleString()} rechazadas</p>
    <ul>
      <li>Peticiones HTTP: {requestCount} (POST + SSE)</li>
      <li>Total estimado: {totalEstimate.toLocaleString()} filas</li>
      <li>Suma USD: ${totalUsd.toLocaleString(undefined, { maximumFractionDigits: 2 })}</li>
      <li>Throughput: {throughput.toFixed(1)} filas/s</li>
      <li>
        Datos en stream gRPC: {formatBytes(bytesStreamed)}
        {#if totalFileBytes > 0}
          <span class="muted">(archivo en disco: {formatBytes(totalFileBytes)})</span>
        {/if}
      </li>
      <li>Bytes SSE recibidos: {formatBytes(bytesTransferred)}</li>
      <li>Throughput stream: {formatBytesPerSec(bytesThroughput)}</li>
    </ul>
  </article>

  <article class="card feed">
    <h2>Feed SSE</h2>
    <div class="feed-list">
      {#if feed.length === 0}
        <p class="empty">Inicia el pipeline para ver eventos SSE.</p>
      {:else}
        {#each feed as entry}
          <div class="feed-item">
            <header>
              <span class="badge">{entry.stage}</span>
              <time>{entry.time}</time>
            </header>
            <p>{entry.message}</p>
            {#if entry.preview}
              <pre>{entry.preview}</pre>
            {/if}
          </div>
        {/each}
      {/if}
    </div>
  </article>
</section>

<style>
  .controls {
    display: grid;
    gap: 0.75rem;
  }

  .control-row {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    color: #94a3b8;
    font-size: 0.95rem;
  }

  code {
    font-size: 0.85rem;
    color: #cbd5e1;
  }

  .error {
    color: #f87171;
  }

  .metrics h2,
  .feed h2 {
    margin: 0 0 0.75rem;
    font-size: 1.05rem;
  }

  .progress-wrap {
    height: 10px;
    background: #1f2937;
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 0.5rem;
  }

  .progress-bar.grpc {
    height: 100%;
    background: linear-gradient(90deg, #2563eb, #22d3ee);
    transition: width 0.25s ease;
  }

  .metrics ul {
    margin: 0.5rem 0 0;
    padding-left: 1.1rem;
    color: #cbd5e1;
  }

  .muted {
    color: #64748b;
    font-size: 0.9em;
  }

  .feed-list {
    max-height: 360px;
    overflow: auto;
    display: grid;
    gap: 0.65rem;
  }

  .feed-item {
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 0.65rem 0.75rem;
    background: #0f172a;
  }

  .feed-item header {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.35rem;
  }

  .badge {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #93c5fd;
  }

  time {
    color: #64748b;
    font-size: 0.8rem;
  }

  .feed-item p {
    margin: 0 0 0.35rem;
    color: #cbd5e1;
    font-size: 0.9rem;
  }

  pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 0.78rem;
    color: #94a3b8;
    background: #020617;
    padding: 0.45rem 0.5rem;
    border-radius: 6px;
  }

  .empty {
    color: #64748b;
    margin: 0;
  }
</style>
