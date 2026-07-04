"""Transform gRPC service: enriches record batches (pure worker)."""

from __future__ import annotations

import logging
import os
from concurrent import futures

import grpc

from generated.pipeline.v1 import pipeline_pb2, pipeline_pb2_grpc
from services.common.limits import grpc_message_options
from services.common.pipeline_utils import (
    preview_record,
    proto_record_to_dict,
    transform_record,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [transform] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

TRANSFORM_PORT = int(os.getenv("TRANSFORM_PORT", "50052"))


class TransformServicer(pipeline_pb2_grpc.TransformServiceServicer):
    def Ping(self, request, context):
        return pipeline_pb2.PingResponse(status="ok")

    def TransformStream(self, request_iterator, context):
        for batch in request_iterator:
            rows_processed = 0
            rows_rejected = 0
            total_usd_delta = 0.0
            last_preview = ""

            for record in batch.records:
                payload = proto_record_to_dict(record)
                transformed, error = transform_record(payload)
                if error:
                    rows_rejected += 1
                else:
                    rows_processed += 1
                    total_usd_delta += transformed["amount_usd"]
                    last_preview = preview_record(transformed)

            yield pipeline_pb2.BatchResult(
                rows_processed=rows_processed,
                rows_rejected=rows_rejected,
                total_usd_delta=round(total_usd_delta, 2),
                record_preview=last_preview,
            )

            logger.info(
                "Batch done job_id=%s chunk=%s/%s processed=%s rejected=%s",
                batch.job_id,
                batch.chunk_index,
                batch.chunk_total,
                rows_processed,
                rows_rejected,
            )


def serve() -> None:
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=8),
        options=grpc_message_options(),
    )
    pipeline_pb2_grpc.add_TransformServiceServicer_to_server(
        TransformServicer(),
        server,
    )
    server.add_insecure_port(f"[::]:{TRANSFORM_PORT}")
    server.start()
    logger.info("Transform service listening on %s", TRANSFORM_PORT)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
