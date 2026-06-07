#!/usr/bin/env python3
"""Generate Python gRPC stubs from proto definitions."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = ROOT / "proto"
OUT_DIR = ROOT / "generated"
PROTO_FILE = PROTO_DIR / "pipeline" / "v1" / "pipeline.proto"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{PROTO_DIR}",
        f"--python_out={OUT_DIR}",
        f"--grpc_python_out={OUT_DIR}",
        str(PROTO_FILE),
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    init_files = [
        OUT_DIR / "__init__.py",
        OUT_DIR / "pipeline" / "__init__.py",
        OUT_DIR / "pipeline" / "v1" / "__init__.py",
    ]
    for init_file in init_files:
        init_file.parent.mkdir(parents=True, exist_ok=True)
        init_file.touch(exist_ok=True)

    pb2_grpc = OUT_DIR / "pipeline" / "v1" / "pipeline_pb2_grpc.py"
    content = pb2_grpc.read_text(encoding="utf-8")
    fixed = content.replace(
        "from pipeline.v1 import pipeline_pb2 as pipeline_dot_v1_dot_pipeline__pb2",
        "from generated.pipeline.v1 import pipeline_pb2 as pipeline_dot_v1_dot_pipeline__pb2",
    )
    pb2_grpc.write_text(fixed, encoding="utf-8")
    print("Proto stubs generated in", OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
