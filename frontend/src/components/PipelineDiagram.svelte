<script lang="ts">
  import { formatBytes, formatBytesPerSec } from './api';

  type Props = {
    activeStage: string;
    rowsProcessed: number;
    throughput: number;
    bytesStreamed: number;
    bytesThroughput: number;
  };

  let {
    activeStage,
    rowsProcessed,
    throughput,
    bytesStreamed,
    bytesThroughput,
  }: Props = $props();

  const nodes = [
    { id: 'ingest', label: 'Ingest Service', subtitle: 'Lee CSV por chunks' },
    { id: 'transform', label: 'Transform Service', subtitle: 'Enriquece registros' },
    { id: 'ui', label: 'Gateway + UI', subtitle: 'SSE en tiempo real' },
  ];
</script>

<section class="card pipeline">
  <h2>Pipeline gRPC</h2>
  <div class="flow">
    {#each nodes as node, index}
      <article class="node" class:active={activeStage === node.id}>
        <div class="pulse"></div>
        <strong>{node.label}</strong>
        <span>{node.subtitle}</span>
      </article>
      {#if index < nodes.length - 1}
        <div class="edge" class:active={activeStage === node.id || activeStage === nodes[index + 1].id}>
          <span class="arrow">→</span>
          {#if index === 0}
            <small>{rowsProcessed.toLocaleString()} filas</small>
            <small>{formatBytes(bytesStreamed)} stream</small>
          {:else if index === 1}
            <small>{throughput.toFixed(1)} filas/s</small>
            <small>{formatBytesPerSec(bytesThroughput)}</small>
          {/if}
        </div>
      {/if}
    {/each}
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
    position: relative;
    min-width: 150px;
    padding: 0.85rem 1rem;
    border-radius: 10px;
    border: 1px solid #334155;
    background: #0f172a;
    display: grid;
    gap: 0.25rem;
  }

  .node.active {
    border-color: #60a5fa;
    box-shadow: 0 0 0 1px #60a5fa inset;
  }

  .node.active .pulse {
    opacity: 1;
    animation: pulse 1s ease-out;
  }

  .pulse {
    position: absolute;
    inset: -2px;
    border-radius: inherit;
    border: 2px solid #3b82f6;
    opacity: 0;
    pointer-events: none;
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
  }

  .edge.active {
    color: #93c5fd;
  }

  .arrow {
    font-size: 1.4rem;
    line-height: 1;
  }

  @keyframes pulse {
    0% {
      transform: scale(1);
      opacity: 0.8;
    }
    100% {
      transform: scale(1.05);
      opacity: 0;
    }
  }
</style>
