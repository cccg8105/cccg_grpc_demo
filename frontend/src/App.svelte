<script lang="ts">
  import ComparisonPanel from './lib/ComparisonPanel.svelte';
  import GrpcTab from './lib/tabs/GrpcTab.svelte';
  import RestTab from './lib/tabs/RestTab.svelte';
  import { upsertRunHistory, type RunMetrics } from './lib/runMetrics';

  let activeTab = $state<'grpc' | 'rest'>('grpc');
  let chunkSize = $state(100);
  let slowMode = $state(true);
  let runHistory = $state<RunMetrics[]>([]);

  function onRunComplete(metrics: RunMetrics) {
    runHistory = upsertRunHistory(runHistory, metrics);
  }
</script>

<main class="page">
  <header>
    <h1>Demo gRPC vs REST</h1>
    <p>Compara pipeline gRPC con streaming frente a APIs REST por lotes orquestadas desde el browser.</p>
  </header>

  <section class="card shared-controls">
    <div class="control-row">
      <div class="tabs">
        <button class:active={activeTab === 'grpc'} onclick={() => (activeTab = 'grpc')}>Pipeline gRPC</button>
        <button class:active={activeTab === 'rest'} onclick={() => (activeTab = 'rest')}>API REST por lotes</button>
      </div>
      <label>
        <input type="checkbox" bind:checked={slowMode} />
        Modo lento
      </label>
      <label>
        Chunk size
        <input type="number" min="10" max="1000" step="10" bind:value={chunkSize} />
      </label>
    </div>
  </section>

  <ComparisonPanel history={runHistory} />

  {#if activeTab === 'grpc'}
    <GrpcTab {chunkSize} {slowMode} onComplete={onRunComplete} />
  {:else}
    <RestTab {chunkSize} {slowMode} onComplete={onRunComplete} />
  {/if}
</main>

<style>
  .page {
    max-width: 1100px;
    margin: 0 auto;
    padding: 1.5rem;
    display: grid;
    gap: 1rem;
  }

  header h1 {
    margin: 0 0 0.25rem;
  }

  header p {
    margin: 0;
    color: #94a3b8;
  }

  .shared-controls {
    display: grid;
    gap: 0.75rem;
  }

  .control-row {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
  }

  .tabs {
    display: flex;
    gap: 0.5rem;
  }

  .tabs button {
    background: #1f2937;
    color: #cbd5e1;
  }

  .tabs button.active {
    background: #3b82f6;
    color: white;
  }

  label {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    color: #cbd5e1;
  }

  input[type='number'] {
    width: 5rem;
    padding: 0.4rem 0.5rem;
    border-radius: 6px;
    border: 1px solid #334155;
    background: #111827;
    color: inherit;
  }
</style>
