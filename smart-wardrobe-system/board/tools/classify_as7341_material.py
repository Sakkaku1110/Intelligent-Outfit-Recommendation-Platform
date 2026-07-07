#!/usr/bin/env python3
"""Classify clothing material from GY-AS7341 JSON or JSONL readings."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Iterable, List


BOARD_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(BOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(BOARD_ROOT))

from app.spectral_material import classify_json_lines, classify_material, has_as7341_channels


def _read_lines(source: str) -> List[str]:
    if source == "-":
        return sys.stdin.read().splitlines()
    path = pathlib.Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8").splitlines()
    return [source]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source",
        help="AS7341 JSON string, JSONL file, or '-' for stdin.",
    )
    parser.add_argument("--top-k", type=int, default=3, help="Number of candidates to print.")
    args = parser.parse_args()

    lines = _read_lines(args.source)
    if len(lines) == 1 and lines[0].strip().startswith("{"):
        payload = json.loads(lines[0])
        if not isinstance(payload, dict) or not has_as7341_channels(payload):
            raise SystemExit("input does not contain f1..f8, clear and nir channels")
        results = [classify_material(payload, top_k=args.top_k)]
    else:
        results = classify_json_lines(lines, top_k=args.top_k)

    for result in results:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
