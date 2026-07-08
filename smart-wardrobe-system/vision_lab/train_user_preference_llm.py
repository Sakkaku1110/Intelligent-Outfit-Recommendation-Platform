#!/usr/bin/env python3
"""Prepare user-preference continuation data for the outfit LLM.

The script is manual-only. It can consume explicit feedback events, or it can
derive weak preference pairs from the wardrobe favorite_score field.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from llm_training import (
    build_preference_tuning_bundle,
    load_feedback_events,
    load_wardrobe_items,
    now_tag,
    validate_jsonl,
)


ROOT = pathlib.Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wardrobe", default=str(ROOT / "demo_wardrobe.json"))
    parser.add_argument("--db", default="", help="Optional board SQLite wardrobe.db path.")
    parser.add_argument("--feedback", default="", help="Optional JSONL/JSON/CSV feedback events.")
    parser.add_argument("--out", default=str(ROOT / "llm_training_runs" / ("user_preference_" + now_tag())))
    parser.add_argument("--base-model", default="qwen2.5-7b-instruct")
    args = parser.parse_args()

    items = load_wardrobe_items(
        wardrobe_path=pathlib.Path(args.wardrobe) if args.wardrobe else None,
        db_path=pathlib.Path(args.db) if args.db else None,
    )
    if not items:
        raise SystemExit("no wardrobe items found")

    feedback = load_feedback_events(pathlib.Path(args.feedback)) if args.feedback else []
    bundle = build_preference_tuning_bundle(
        items=items,
        output_dir=pathlib.Path(args.out),
        base_model=args.base_model,
        feedback_events=feedback,
    )
    dpo_file = pathlib.Path(bundle.files["preference_dpo"])
    sft_file = pathlib.Path(bundle.files["continue_sft"])
    validate_jsonl(dpo_file)
    validate_jsonl(sft_file)
    print("mode=%s" % bundle.mode)
    print("items=%d" % len(items))
    print("feedback_events=%d" % len(feedback))
    print("preference_pairs=%d" % bundle.examples)
    print("dpo_jsonl=%s" % dpo_file)
    print("continue_sft_jsonl=%s" % sft_file)
    print("manifest=%s" % bundle.manifest_path)
    print("training_started=false")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
