import { createEmptyRunMetrics, finalizeRunMetrics, type RunMetrics } from './runMetrics';

const ingestUrl = import.meta.env.VITE_REST_INGEST_URL ?? 'http://localhost:8091';
const transformUrl = import.meta.env.VITE_REST_TRANSFORM_URL ?? 'http://localhost:8092';
const filePath = '/data/transactions.csv';

export type FeedEntry = {
  time: string;
  stage: string;
  message: string;
  preview: string;
};

export type RestProgressUpdate = {
  feedEntry: FeedEntry;
  rowsProcessed: number;
  rowsRejected: number;
  totalUsd: number;
  totalRows: number;
  totalFileBytes: number;
  bytesTransferred: number;
  requestCount: number;
  activeStage: string;
  batchIndex: number;
  batchTotal: number;
};

type MetaResponse = {
  total_rows: number;
  total_file_bytes: number;
  response_bytes: number;
};

type RecordsResponse = {
  offset: number;
  limit: number;
  total_rows: number;
  total_file_bytes: number;
  records: Record<string, string>[];
  has_more: boolean;
  response_bytes: number;
};

type TransformResponse = {
  transformed: Record<string, unknown>[];
  rows_processed: number;
  rows_rejected: number;
  total_usd_delta: number;
  record_preview: string;
  response_bytes: number;
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function nowTime(): string {
  return new Date().toLocaleTimeString();
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<{ data: T; bytes: number }> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}): ${url}`);
  }
  const text = await response.text();
  return {
    data: JSON.parse(text) as T,
    bytes: new TextEncoder().encode(text).length,
  };
}

export async function runRestBatchPipeline(options: {
  chunkSize: number;
  sleepMs: number;
  onProgress: (update: RestProgressUpdate) => void;
}): Promise<RunMetrics> {
  const startMs = performance.now();
  let firstUpdateMs: number | null = null;
  let requestCount = 0;
  let bytesTransferred = 0;
  let rowsProcessed = 0;
  let rowsRejected = 0;
  let totalUsd = 0.0;
  let totalRows = 0;
  let totalFileBytes = 0;

  const metrics = createEmptyRunMetrics('rest', options.chunkSize, options.sleepMs > 0);

  const metaResult = await fetchJson<MetaResponse>(
    `${ingestUrl}/meta?file_path=${encodeURIComponent(filePath)}`,
  );
  requestCount += 1;
  bytesTransferred += metaResult.bytes;
  totalRows = metaResult.data.total_rows;
  totalFileBytes = metaResult.data.total_file_bytes;

  const batchTotal = Math.max(Math.ceil(totalRows / options.chunkSize), 1);
  let offset = 0;
  let batchIndex = 0;

  while (offset < totalRows) {
    batchIndex += 1;

    const recordsResult = await fetchJson<RecordsResponse>(
      `${ingestUrl}/records?offset=${offset}&limit=${options.chunkSize}&file_path=${encodeURIComponent(filePath)}`,
    );
    requestCount += 1;
    bytesTransferred += recordsResult.bytes;

    const transformResult = await fetchJson<TransformResponse>(`${transformUrl}/transform`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ records: recordsResult.data.records }),
    });
    requestCount += 1;
    bytesTransferred += transformResult.bytes;

    rowsProcessed += transformResult.data.rows_processed;
    rowsRejected += transformResult.data.rows_rejected;
    totalUsd += transformResult.data.total_usd_delta;

    const feedEntry: FeedEntry = {
      time: nowTime(),
      stage: 'rest',
      message: `Lote ${batchIndex}/${batchTotal}: GET /records?offset=${offset} → POST /transform (${recordsResult.data.records.length} filas)`,
      preview: transformResult.data.record_preview ?? '',
    };

    if (firstUpdateMs === null) {
      firstUpdateMs = performance.now();
    }

    options.onProgress({
      feedEntry,
      rowsProcessed,
      rowsRejected,
      totalUsd,
      totalRows,
      totalFileBytes,
      bytesTransferred,
      requestCount,
      activeStage: recordsResult.data.has_more ? 'ingest' : 'complete',
      batchIndex,
      batchTotal,
    });

    offset += recordsResult.data.records.length;
    if (!recordsResult.data.has_more || recordsResult.data.records.length === 0) {
      break;
    }

    if (options.sleepMs > 0) {
      await sleep(options.sleepMs);
    }
  }

  metrics.totalRows = totalRows;
  metrics.rowsProcessed = rowsProcessed;
  metrics.rowsRejected = rowsRejected;
  metrics.totalUsd = totalUsd;
  metrics.requestCount = requestCount;
  metrics.bytesTransferred = bytesTransferred;

  return finalizeRunMetrics(metrics, startMs, firstUpdateMs);
}
