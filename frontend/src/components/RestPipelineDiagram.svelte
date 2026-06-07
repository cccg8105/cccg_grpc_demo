<script lang="ts">
  import { formatBytes } from './api';

  type Props = {
    activeStage: string;
    rowsProcessed: number;
    requestCount: number;
    bytesTransferred: number;
    batchIndex: number;
    batchTotal: number;
  };

  let {
    activeStage,
    rowsProcessed,
    requestCount,
    bytesTransferred,
    batchIndex,
    batchTotal,
  }: Props = $props();
</script>

<section class="card pipeline">
  <h2>API REST por lotes</h2>
  <div class="flow">
    <article class="node" class:active={activeStage === 'browser'}>
      <strong>Browser</strong>
      <span>Loop fetch por lote</span>
    </article>
    <div class="edge" class:active={activeStage === 'browser' || activeStage === 'ingest'}>
      <span class="arrow">→</span>
      <small>{requestCount} requests</small>
    </div>
    <article class="node" class:active={activeStage === 'ingest'}>
      <strong>rest-ingest</strong>
      <span>GET /records</span>
    </article>
    <div class="edge" class:active={activeStage === 'ingest' || activeStage === 'transform'}>
      <span class="arrow">→</span>
      <small>lote {batchIndex}/{batchTotal}</small>
    </div>
    <article class="node" class:active={activeStage === 'transform'}>
      <strong>rest-transform</strong>
      <span>POST /transform</span>
    </article>
    <div class="edge" class:active={activeStage === 'complete'}>
      <span class="arrow">→</span>
      <small>{formatBytes(bytesTransferred)}</small>
    </div>
    <article class="node" class:active={activeStage === 'complete'}>
      <strong>UI</strong>
      <span>{rowsProcessed.toLocaleString()} filas</span>
    </article>
  </div>
</section>

<style>
  .pipeline h2 {
    margin: 0 0 1rem;
    font-size: 1.1rem;
  }

  .flow {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
  }

  .node {
    min-width: 130px;
    padding: 0.85rem 1rem;
    border-radius: 10px;
    border: 1px solid #334155;
    background: #0f172a;
    display: grid;
    gap: 0.25rem;
  }

  .node.active {
    border-color: #34d399;
    box-shadow: 0 0 0 1px #34d399 inset;
  }

  .node span {
    color: #94a3b8;
    font-size: 0.85rem;
  }

  .edge {
    display: grid;
    justify-items: center;
    gap: 0.15rem;
    min-width: 70px;
    color: #64748b;
    font-size: 0.8rem;
  }

  .edge.active {
    color: #6ee7b7;
  }

  .arrow {
    font-size: 1.4rem;
    line-height: 1;
  }
</style>
