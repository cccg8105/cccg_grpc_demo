export type RunMode = 'grpc' | 'rest';

export type RunMetrics = {
  mode: RunMode;
  chunkSize: number;
  slowMode: boolean;
  totalRows: number;
  rowsProcessed: number;
  rowsRejected: number;
  totalUsd: number;
  wallClockMs: number;
  timeToFirstUpdateMs: number;
  requestCount: number;
  bytesTransferred: number;
  throughputRowsPerSec: number;
  throughputBytesPerSec: number;
};

export function createEmptyRunMetrics(mode: RunMode, chunkSize: number, slowMode: boolean): RunMetrics {
  return {
    mode,
    chunkSize,
    slowMode,
    totalRows: 0,
    rowsProcessed: 0,
    rowsRejected: 0,
    totalUsd: 0,
    wallClockMs: 0,
    timeToFirstUpdateMs: 0,
    requestCount: 0,
    bytesTransferred: 0,
    throughputRowsPerSec: 0,
    throughputBytesPerSec: 0,
  };
}

export function finalizeRunMetrics(
  base: RunMetrics,
  startMs: number,
  firstUpdateMs: number | null,
): RunMetrics {
  const wallClockMs = performance.now() - startMs;
  const elapsedSec = Math.max(wallClockMs / 1000, 0.001);
  return {
    ...base,
    wallClockMs,
    timeToFirstUpdateMs: firstUpdateMs !== null ? firstUpdateMs - startMs : wallClockMs,
    throughputRowsPerSec: base.rowsProcessed / elapsedSec,
    throughputBytesPerSec: base.bytesTransferred / elapsedSec,
  };
}

export function formatMs(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)} s`;
  }
  return `${Math.round(value)} ms`;
}

export function formatDiff(grpcValue: number, restValue: number, asPercent = false): string {
  if (grpcValue === 0 && restValue === 0) {
    return '—';
  }
  const diff = restValue - grpcValue;
  if (asPercent) {
    if (grpcValue === 0) {
      return '—';
    }
    const pct = ((diff / grpcValue) * 100).toFixed(0);
    return diff >= 0 ? `+${pct}%` : `${pct}%`;
  }
  const sign = diff >= 0 ? '+' : '';
  return `${sign}${diff.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function upsertRunHistory(history: RunMetrics[], entry: RunMetrics): RunMetrics[] {
  return [...history.filter((item) => item.mode !== entry.mode), entry];
}

export function getLatestByMode(history: RunMetrics[], mode: RunMode): RunMetrics | undefined {
  return history.find((item) => item.mode === mode);
}
