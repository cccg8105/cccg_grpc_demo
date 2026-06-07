<script lang="ts">
  import { formatBytes } from './api';
  import { formatDiff, formatMs, getLatestByMode, type RunMetrics } from './runMetrics';

  type Props = {
    history: RunMetrics[];
  };

  let { history }: Props = $props();

  let grpcRun = $derived(getLatestByMode(history, 'grpc'));
  let restRun = $derived(getLatestByMode(history, 'rest'));
  let hasComparison = $derived(Boolean(grpcRun && restRun));

  type Row = {
    label: string;
    grpc: string;
    rest: string;
    diff: string;
  };

  let rows = $derived.by((): Row[] => {
    if (!grpcRun || !restRun) {
      return [];
    }
    return [
      {
        label: 'Tiempo total',
        grpc: formatMs(grpcRun.wallClockMs),
        rest: formatMs(restRun.wallClockMs),
        diff: formatDiff(grpcRun.wallClockMs, restRun.wallClockMs, true),
      },
      {
        label: 'Tiempo al 1er update',
        grpc: formatMs(grpcRun.timeToFirstUpdateMs),
        rest: formatMs(restRun.timeToFirstUpdateMs),
        diff: formatDiff(grpcRun.timeToFirstUpdateMs, restRun.timeToFirstUpdateMs, true),
      },
      {
        label: 'Peticiones HTTP',
        grpc: String(grpcRun.requestCount),
        rest: String(restRun.requestCount),
        diff: formatDiff(grpcRun.requestCount, restRun.requestCount),
      },
      {
        label: 'Bytes recibidos',
        grpc: formatBytes(grpcRun.bytesTransferred),
        rest: formatBytes(restRun.bytesTransferred),
        diff: formatDiff(grpcRun.bytesTransferred, restRun.bytesTransferred, true),
      },
      {
        label: 'Filas procesadas',
        grpc: grpcRun.rowsProcessed.toLocaleString(),
        rest: restRun.rowsProcessed.toLocaleString(),
        diff: formatDiff(grpcRun.rowsProcessed, restRun.rowsProcessed),
      },
      {
        label: 'Throughput filas/s',
        grpc: grpcRun.throughputRowsPerSec.toFixed(1),
        rest: restRun.throughputRowsPerSec.toFixed(1),
        diff: formatDiff(grpcRun.throughputRowsPerSec, restRun.throughputRowsPerSec, true),
      },
    ];
  });
</script>

<section class="card comparison">
  <h2>Comparativa objetiva</h2>

  {#if history.length === 0}
    <p class="hint">Ejecuta al menos un modo para registrar métricas.</p>
  {:else if !hasComparison}
    <p class="hint">
      Modo {grpcRun ? 'gRPC' : 'REST'} registrado. Cambia de pestaña y ejecuta el otro modo para ver la tabla comparativa.
    </p>
    {#if grpcRun}
      <ul class="single-run">
        <li>gRPC — {formatMs(grpcRun.wallClockMs)}, {grpcRun.requestCount} peticiones, {formatBytes(grpcRun.bytesTransferred)}</li>
      </ul>
    {/if}
    {#if restRun}
      <ul class="single-run">
        <li>REST — {formatMs(restRun.wallClockMs)}, {restRun.requestCount} peticiones, {formatBytes(restRun.bytesTransferred)}</li>
      </ul>
    {/if}
  {:else}
    <p class="hint">
      Misma config: chunk {grpcRun?.chunkSize}, modo lento {grpcRun?.slowMode ? 'sí' : 'no'}.
      Diff = REST vs gRPC (positivo = REST más costoso).
    </p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>KPI</th>
            <th>gRPC</th>
            <th>REST</th>
            <th>Diff</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row}
            <tr>
              <td>{row.label}</td>
              <td>{row.grpc}</td>
              <td>{row.rest}</td>
              <td class="diff">{row.diff}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

<style>
  .comparison h2 {
    margin: 0 0 0.75rem;
    font-size: 1.05rem;
  }

  .hint {
    margin: 0;
    color: #94a3b8;
    font-size: 0.95rem;
  }

  .single-run {
    margin: 0.75rem 0 0;
    padding-left: 1.1rem;
    color: #cbd5e1;
  }

  .table-wrap {
    margin-top: 0.75rem;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
  }

  th,
  td {
    border: 1px solid #1f2937;
    padding: 0.55rem 0.65rem;
    text-align: left;
  }

  th {
    background: #0f172a;
    color: #93c5fd;
  }

  td {
    color: #cbd5e1;
  }

  .diff {
    color: #fbbf24;
    font-variant-numeric: tabular-nums;
  }
</style>
