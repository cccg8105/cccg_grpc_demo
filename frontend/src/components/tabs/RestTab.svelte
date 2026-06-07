<script lang="ts">
  import { formatBytes, progressPercent } from '../api';
  import RestPipelineDiagram from '../RestPipelineDiagram.svelte';
  import { runRestBatchPipeline, type FeedEntry } from '../restBatchClient';
  import type { RunMetrics } from '../runMetrics';

  type Props = {
    chunkSize: number;
    slowMode: boolean;
    onComplete: (metrics: RunMetrics) => void;
  };

  let { chunkSize, slowMode, onComplete }: Props = $props();

  let running = $state(false);
  let status = $state('idle');
  let activeStage = $state('');
  let rowsProcessed = $state(0);
  let rowsRejected = $state(0);
  let totalUsd = $state(0);
  let totalEstimate = $state(0);
  let totalFileBytes = $state(0);
  let requestCount = $state(0);
  let bytesTransferred = $state(0);
  let batchIndex = $state(0);
  let batchTotal = $state(0);
  let errorMessage = $state('');
  let feed = $state.raw<FeedEntry[]>([]);

  let percent = $derived(progressPercent(rowsProcessed + rowsRejected, totalEstimate));

  function resetMetrics() {
    rowsProcessed = 0;
    rowsRejected = 0;
    totalUsd = 0;
    totalEstimate = 0;
    totalFileBytes = 0;
    requestCount = 0;
    bytesTransferred = 0;
    batchIndex = 0;
    batchTotal = 0;
    activeStage = 'browser';
    feed = [];
    errorMessage = '';
  }

  async function onStart() {
    if (running) return;

    resetMetrics();
    running = true;
    status = 'running';
    activeStage = 'browser';

    try {
      const sleepMs = slowMode ? 80 : 0;
      const metrics = await runRestBatchPipeline({
        chunkSize,
        sleepMs,
        onProgress: (update) => {
          rowsProcessed = update.rowsProcessed;
          rowsRejected = update.rowsRejected;
          totalUsd = update.totalUsd;
          totalEstimate = update.totalRows;
          totalFileBytes = update.totalFileBytes;
          requestCount = update.requestCount;
          bytesTransferred = update.bytesTransferred;
          batchIndex = update.batchIndex;
          batchTotal = update.batchTotal;
          activeStage = update.activeStage === 'complete' ? 'complete' : 'transform';
          feed = [update.feedEntry, ...feed].slice(0, 80);
        },
      });

      status = 'complete';
      activeStage = 'complete';
      onComplete(metrics);
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Unknown error';
      status = 'error';
    } finally {
      running = false;
    }
  }
</script>

<section class="card controls">
  <div class="control-row">
    <button onclick={onStart} disabled={running}>Iniciar loop REST</button>
  </div>
  <div class="meta">
    <span>Estado: <strong>{status}</strong></span>
    <span>Peticiones: <strong>{requestCount}</strong></span>
    {#if errorMessage}<span class="error">{errorMessage}</span>{/if}
  </div>
</section>

<RestPipelineDiagram
  {activeStage}
  {rowsProcessed}
  {requestCount}
  {bytesTransferred}
  {batchIndex}
  {batchTotal}
/>

<section class="grid grid-2">
  <article class="card metrics">
    <h2>Métricas REST</h2>
    <div class="progress-wrap">
      <div class="progress-bar rest" style={`width: ${percent}%`}></div>
    </div>
    <p>{percent}% — {rowsProcessed.toLocaleString()} OK / {rowsRejected.toLocaleString()} rechazadas</p>
    <ul>
      <li>Peticiones HTTP: {requestCount} (meta + 2 por lote)</li>
      <li>Total estimado: {totalEstimate.toLocaleString()} filas</li>
      <li>Suma USD: ${totalUsd.toLocaleString(undefined, { maximumFractionDigits: 2 })}</li>
      <li>Lotes: {batchIndex} / {batchTotal || '—'}</li>
      <li>
        Bytes HTTP recibidos: {formatBytes(bytesTransferred)}
        {#if totalFileBytes > 0}
          <span class="muted">(archivo en disco: {formatBytes(totalFileBytes)})</span>
        {/if}
      </li>
    </ul>
  </article>

  <article class="card feed">
    <h2>Feed de peticiones</h2>
    <div class="feed-list">
      {#if feed.length === 0}
        <p class="empty">Inicia el loop REST para ver cada GET/POST.</p>
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

  .progress-bar.rest {
    height: 100%;
    background: linear-gradient(90deg, #059669, #34d399);
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
    color: #6ee7b7;
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
