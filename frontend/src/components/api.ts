export type ProgressEvent = {
  job_id?: string;
  stage?: string;
  timestamp_ms?: number;
  record_preview?: string;
  rows_processed?: number;
  rows_rejected?: number;
  total_usd?: number;
  total_rows_estimate?: number;
  throughput_rows_per_sec?: number;
  job_complete?: boolean;
  message?: string;
  type?: string;
  bytes_streamed?: number;
  total_file_bytes?: number;
  throughput_bytes_per_sec?: number;
};

export type FeedEntry = {
  time: string;
  stage: string;
  message: string;
  preview: string;
};

const gatewayUrl = import.meta.env.VITE_GATEWAY_URL ?? 'http://localhost:8080';

export async function startJob(options: {
  chunkSize: number;
  sleepMs: number;
}): Promise<{ job_id: string }> {
  const response = await fetch(`${gatewayUrl}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_path: '/data/transactions.csv',
      chunk_size: options.chunkSize,
      sleep_ms: options.sleepMs,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to start job (${response.status})`);
  }

  return response.json();
}

export function subscribeToJob(
  jobId: string,
  onEvent: (event: ProgressEvent) => void,
  onError: (error: Error) => void,
): () => void {
  const source = new EventSource(`${gatewayUrl}/jobs/${jobId}/events`);

  source.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data));
    } catch (error) {
      onError(error instanceof Error ? error : new Error('Invalid SSE payload'));
    }
  };

  source.onerror = () => {
    onError(new Error('SSE connection error'));
    source.close();
  };

  return () => source.close();
}

export function formatTime(timestampMs?: number): string {
  if (!timestampMs) {
    return new Date().toLocaleTimeString();
  }
  return new Date(timestampMs).toLocaleTimeString();
}

export function progressPercent(processed: number, total: number): number {
  if (!total) {
    return 0;
  }
  return Math.min(100, Math.round((processed / total) * 100));
}

export function formatBytes(value: number): string {
  if (value >= 1_048_576) {
    return `${(value / 1_048_576).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${value} B`;
}

export function formatBytesPerSec(value: number): string {
  return `${formatBytes(value)}/s`;
}
