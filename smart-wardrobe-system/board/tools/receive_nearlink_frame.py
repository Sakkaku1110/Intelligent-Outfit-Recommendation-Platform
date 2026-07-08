#!/usr/bin/env python3
"""Receive WS63 AS7341 binary frames and classify them on the SS928 side.

In production the byte stream can come from a NearLink SDK callback. For bench
testing, this script can read from a serial-like device or stdin.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import BinaryIO, Iterable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board.app.nearlink_frame import FRAME_SIZE, iter_spectral_frames  # noqa: E402
from board.app.spectral_material import classify_material  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode WS63 NearLink AS7341 binary frames for SS928 processing."
    )
    parser.add_argument(
        "--input",
        help="Binary stream path. Omit to read from stdin.buffer.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=FRAME_SIZE,
        help="Read chunk size in bytes.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print decoded sensor payloads without material classification.",
    )
    return parser.parse_args()


def read_chunks(stream: BinaryIO, chunk_size: int) -> Iterable[bytes]:
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        yield chunk


def process_stream(stream: BinaryIO, chunk_size: int, raw: bool) -> None:
    for frame in iter_spectral_frames(read_chunks(stream, chunk_size)):
        payload = frame.to_payload()
        output = payload if raw else {**payload, "material_hint": classify_material(payload)}
        print(json.dumps(output, ensure_ascii=False), flush=True)


def main() -> None:
    args = parse_args()
    chunk_size = max(1, int(args.chunk_size))
    if args.input:
        with open(args.input, "rb") as stream:
            process_stream(stream, chunk_size, args.raw)
    else:
        process_stream(sys.stdin.buffer, chunk_size, args.raw)


if __name__ == "__main__":
    main()
