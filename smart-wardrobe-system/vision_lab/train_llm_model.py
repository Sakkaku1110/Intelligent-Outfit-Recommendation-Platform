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
from llm_trainer import LoraTrainingConfig, run_lora_training


ROOT = pathlib.Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wardrobe", default=str(ROOT / "demo_wardrobe.json"))
    parser.add_argument("--db", default="", help="Optional board SQLite wardrobe.db path.")
    parser.add_argument("--out", default=str(ROOT / "llm_training_runs" / ("base_sft_" + now_tag())))
    parser.add_argument("--base-model", default="qwen2.5-7b-instruct")
    parser.add_argument("--max-examples", type=int, default=0)
    parser.add_argument("--run-training", action="store_true", help="Launch LoRA SFT after writing JSONL.")
    parser.add_argument("--model-out", default="", help="Output directory for LoRA adapter checkpoints.")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
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
    if args.run_training:
        model_out = pathlib.Path(args.model_out) if args.model_out else pathlib.Path(args.out) / "lora_sft_adapter"
        result = run_lora_training(
            LoraTrainingConfig(
                mode="sft",
                train_file=train_file,
                output_dir=model_out,
                base_model=args.base_model,
                epochs=args.epochs,
                learning_rate=args.learning_rate,
                batch_size=args.batch_size,
                gradient_accumulation_steps=args.gradient_accumulation_steps,
                max_seq_length=args.max_seq_length,
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
