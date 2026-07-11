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
from llm_trainer import LoraTrainingConfig, run_lora_training


ROOT = pathlib.Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wardrobe", default=str(ROOT / "demo_wardrobe.json"))
    parser.add_argument("--db", default="", help="Optional board SQLite wardrobe.db path.")
    parser.add_argument("--feedback", default="", help="Optional JSONL/JSON/CSV feedback events.")
    parser.add_argument("--out", default=str(ROOT / "llm_training_runs" / ("user_preference_" + now_tag())))
    parser.add_argument("--base-model", default="qwen2.5-7b-instruct")
    parser.add_argument("--run-training", action="store_true", help="Launch LoRA training after writing JSONL.")
    parser.add_argument("--training-method", choices=["dpo", "sft"], default="dpo")
    parser.add_argument("--model-out", default="", help="Output directory for LoRA adapter checkpoints.")
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--max-prompt-length", type=int, default=1024)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate training inputs without loading a model.")
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
    if args.run_training:
        if bundle.examples <= 0:
            print("training_started=false")
            print("reason=no_preference_pairs")
            print("hint=provide --feedback with like/dislike, chosen/rejected, or rating events before running preference training")
            return 0
        train_file = dpo_file if args.training_method == "dpo" else sft_file
        model_out = pathlib.Path(args.model_out) if args.model_out else pathlib.Path(args.out) / ("lora_%s_adapter" % args.training_method)
        result = run_lora_training(
            LoraTrainingConfig(
                mode=args.training_method,
                train_file=train_file,
                output_dir=model_out,
                base_model=args.base_model,
                epochs=args.epochs,
                learning_rate=args.learning_rate,
                batch_size=args.batch_size,
                gradient_accumulation_steps=args.gradient_accumulation_steps,
                max_seq_length=args.max_seq_length,
                max_prompt_length=args.max_prompt_length,
                lora_rank=args.lora_rank,
                load_in_4bit=args.load_in_4bit,
                bf16=args.bf16,
                fp16=args.fp16,
                dry_run=args.dry_run,
            )
        )
        print("training_started=%s" % str(result["training_started"]).lower())
        print("adapter_dir=%s" % result["output_dir"])
    else:
        print("training_started=false")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
