"""Ingest gRPC service: lee el CSV fila por fila y emite un stream de RawRecord hacia Transform.

Flujo:
1. El gateway llama a `StartPipeline` (unary RPC).
2. Ingest arranca un hilo que abre el CSV y hace client-streaming hacia Transform.
3. Cada X filas (chunk_size) puede introducir un sleep artificial (sleep_ms)
   para ralentizar la demo y que el streaming sea visible en la UI.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import threading
import time
from concurrent import futures
from pathlib import Path

import grpc

from generated.pipeline.v1 import pipeline_pb2, pipeline_pb2_grpc
from services.common.csv_batch import file_meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ingest] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

TRANSFORM_TARGET = os.getenv("TRANSFORM_TARGET", "transform-service:50052")
INGEST_PORT = int(os.getenv("INGEST_PORT", "50051"))
PROGRESS_EVERY = int(os.getenv("PROGRESS_EVERY", "50"))


class IngestServicer(pipeline_pb2_grpc.IngestServiceServicer):
    def Ping(self, request, context):
        return pipeline_pb2.PingResponse(status="ok")

    def StartPipeline(self, request, context):
        job_id = request.job_id
        file_path = request.file_path or "/data/transactions.csv"
        chunk_size = request.chunk_size or 100
        sleep_ms = request.sleep_ms or 0

        if not Path(file_path).exists():
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"file not found: {file_path}")
            return pipeline_pb2.StartPipelineResponse()

        thread = threading.Thread(
            target=self._run_pipeline,
            args=(job_id, file_path, chunk_size, sleep_ms),
            daemon=True,
        )
        thread.start()
        logger.info("Started pipeline job_id=%s file=%s", job_id, file_path)
        return pipeline_pb2.StartPipelineResponse(job_id=job_id, status="started")

    def _run_pipeline(
        self,
        job_id: str,
        file_path: str,
        chunk_size: int,
        sleep_ms: int,
    ) -> None:
        """Hilo worker que ejecuta el pipeline: CSV -> TransformStream gRPC.

        Abre un canal gRPC hacia transform-service y envía todas las filas del CSV
        como mensajes RawRecord. Al finalizar, recibe un TransformSummary.
        """
        channel = grpc.insecure_channel(TRANSFORM_TARGET)
        stub = pipeline_pb2_grpc.TransformServiceStub(channel)

        def record_generator():
            """Generador que produce RawRecord protobuf por cada fila del CSV.

            Implementación row-by-row con csv.DictReader + generador Python:
            - Memoria O(1) por fila, sin DataFrame completo en RAM.
            - Cada fila se serializa a JSON (payload_json) para enviarla por gRPC.
            - bytes_read acumula el tamaño JSON enviado (métrica de stream).
            - Respeta chunk_size: tras procesar N filas puede dormir sleep_ms
              para ralentizar la demo (modo lento visible en UI).

            Nota: no se usa Polars ni pandas porque el looping natural de csv.DictReader
            ya es eficiente para este flujo continuo y evita dependencias pesadas.
            """
            meta = file_meta(file_path)
            total_estimate = meta["total_rows"]
            total_file_bytes = meta["total_file_bytes"]
            bytes_read = 0
            chunk_count = 0
            emitted = 0

            with open(file_path, newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for line_number, row in enumerate(reader, start=2):
                    payload = json.dumps(row, ensure_ascii=True)
                    bytes_read += len(payload.encode("utf-8"))
                    emitted += 1
                    chunk_count += 1

                    yield pipeline_pb2.RawRecord(
                        job_id=job_id,
                        line_number=line_number,
                        payload_json=payload,
                        bytes_read=bytes_read,
                        total_rows_estimate=total_estimate,
                        total_file_bytes=total_file_bytes,
                    )

                    if chunk_count >= chunk_size:
                        chunk_count = 0
                        if sleep_ms > 0:
                            time.sleep(sleep_ms / 1000.0)

            logger.info(
                "Finished streaming job_id=%s rows=%s bytes=%s",
                job_id,
                emitted,
                bytes_read,
            )

        try:
            summary = stub.TransformStream(record_generator())
            logger.info(
                "Transform complete job_id=%s processed=%s rejected=%s total_usd=%.2f",
                job_id,
                summary.rows_processed,
                summary.rows_rejected,
                summary.total_usd,
            )
        except grpc.RpcError as exc:
            logger.error("Pipeline failed job_id=%s error=%s", job_id, exc)
        finally:
            channel.close()


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pipeline_pb2_grpc.add_IngestServiceServicer_to_server(
        IngestServicer(),
        server,
    )
    server.add_insecure_port(f"[::]:{INGEST_PORT}")
    server.start()
    logger.info("Ingest service listening on %s", INGEST_PORT)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
