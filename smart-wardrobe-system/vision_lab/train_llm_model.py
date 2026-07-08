#!/usr/bin/env python3
"""Prepare base LLM training data for outfit recommendation.

This script does not run during board startup. It only writes training-ready
JSONL files and a manifest when a developer calls it manually.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from llm_training import build_base_sft_bundle, load_wardrobe_items, now_tag, validate_jsonl


ROOT = pathlib.Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wardrobe", default=str(ROOT / "demo_wardrobe.json"))
    parser.add_argument("--db", default="", help="Optional board SQLite wardrobe.db path.")
    parser.add_argument("--out", default=str(ROOT / "llm_training_runs" / ("base_sft_" + now_tag())))
    parser.add_argument("--base-model", default="qwen2.5-7b-instruct")
    parser.add_argument("--max-examples", type=int, default=0)
    args = parser.parse_args()

    items = load_wardrobe_items(
        wardrobe_path=pathlib.Path(args.wardrobe) if args.wardrobe else None,
        db_path=pathlib.Path(args.db) if args.db else None,
    )
    if not items:
        raise SystemExit("no wardrobe items found")

    bundle = build_base_sft_bundle(
        items=items,
        output_dir=pathlib.Path(args.out),
        base_model=args.base_model,
        max_examples=max(0, args.max_examples),
    )
    train_file = pathlib.Path(bundle.files["sft_train"])
    validate_jsonl(train_file)
    print("mode=%s" % bundle.mode)
    print("items=%d" % len(items))
    print("examples=%d" % bundle.examples)
    print("train_jsonl=%s" % train_file)
    print("manifest=%s" % bundle.manifest_path)
    print("training_started=false")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
