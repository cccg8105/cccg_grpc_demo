"""Shared validation limits for pipeline chunk/batch sizes."""

MIN_CHUNK_SIZE = 1
MAX_CHUNK_SIZE = 80000

# gRPC default is 4 MiB; RecordBatch with MAX_CHUNK_SIZE rows can exceed that.
MAX_GRPC_MESSAGE_BYTES = 64 * 1024 * 1024


def grpc_message_options() -> list[tuple[str, int]]:
    """Channel/server options for large RecordBatch streaming."""
    return [
        ("grpc.max_send_message_length", MAX_GRPC_MESSAGE_BYTES),
        ("grpc.max_receive_message_length", MAX_GRPC_MESSAGE_BYTES),
    ]
