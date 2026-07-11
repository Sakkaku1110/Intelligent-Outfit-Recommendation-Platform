#!/usr/bin/env python3
"""Convert Polyvore Outfits data into smart-wardrobe LLM SFT/DPO JSONL files."""

from __future__ import annotations

import argparse
import pathlib
import sys

from llm_training import (
    build_polyvore_item_index,
    build_polyvore_preference_pairs,
    build_polyvore_sft_examples,
    load_polyvore_metadata,
    now_tag,
    read_json,
    validate_jsonl,
    write_bundle_manifest,
    write_json,
    write_jsonl,
)


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_POLYVORE_ROOT = ROOT / "data" / "polyvore-outfits"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--polyvore-root", default=str(DEFAULT_POLYVORE_ROOT))
    parser.add_argument("--split", choices=["nondisjoint", "disjoint"], default="disjoint")
    parser.add_argument("--subset", choices=["train", "valid", "test"], default="train")
    parser.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent / "llm_training_runs" / ("polyvore_" + now_tag())))
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-sft-examples", type=int, default=20000)
    parser.add_argument("--max-dpo-pairs", type=int, default=50000)
    args = parser.parse_args()

    polyvore_root = pathlib.Path(args.polyvore_root)
    split_dir = polyvore_root / args.split
    subset_name = "valid" if args.subset == "valid" else args.subset
    outfit_path = split_dir / ("%s.json" % subset_name)
    fitb_path = split_dir / ("fill_in_blank_%s.json" % subset_name)
    metadata_path = polyvore_root / "polyvore_item_metadata.json"
    if not outfit_path.exists():
        raise SystemExit("outfit split not found: %s" % outfit_path)
    if not fitb_path.exists():
        raise SystemExit("fill-in-blank split not found: %s" % fitb_path)
    if not metadata_path.exists():
        raise SystemExit("metadata not found: %s" % metadata_path)

    output_dir = pathlib.Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    outfit_rows = read_json(outfit_path)
    fitb_rows = read_json(fitb_path)
    if not isinstance(outfit_rows, list) or not isinstance(fitb_rows, list):
        raise SystemExit("Polyvore split files must contain JSON arrays")
    metadata = load_polyvore_metadata(metadata_path)
    item_index = build_polyvore_item_index(outfit_rows, metadata)
    sft_examples = build_polyvore_sft_examples(
        fitb_rows,
        item_index,
        max_examples=max(0, args.max_sft_examples),
    )
    dpo_pairs = build_polyvore_preference_pairs(
        fitb_rows,
        item_index,
        max_pairs=max(0, args.max_dpo_pairs),
    )
    sft_path = output_dir / "polyvore_outfit_sft_train.jsonl"
    dpo_path = output_dir / "polyvore_outfit_dpo_train.jsonl"
    sft_count = write_jsonl(sft_path, sft_examples)
    dpo_count = write_jsonl(dpo_path, dpo_pairs)
    files = {
        "sft_train": str(sft_path),
        "preference_dpo": str(dpo_path),
        "source_outfits": str(outfit_path),
        "source_fill_in_blank": str(fitb_path),
        "source_metadata": str(metadata_path),
    }
    write_json(
        output_dir / "polyvore_conversion_summary.json",
        {
            "split": args.split,
            "subset": args.subset,
            "source_outfits": len(outfit_rows),
            "source_fill_in_blank": len(fitb_rows),
            "indexed_items": len(item_index),
            "sft_examples": sft_count,
            "dpo_pairs": dpo_count,
        },
    )
    manifest_path = write_bundle_manifest(
        output_dir,
        "polyvore_outfit_sft_dpo",
        files,
        args.base_model,
        sft_count + dpo_count,
        [
            "SFT rows teach the model to complete a partially observed outfit.",
            "DPO rows use Polyvore fill-in-the-blank distractors as rejected answers.",
            "Use disjoint split for a stricter item-level generalization evaluation.",
        ],
    )
    validate_jsonl(sft_path)
    validate_jsonl(dpo_path)
    print("mode=polyvore_outfit_sft_dpo")
    print("split=%s" % args.split)
    print("subset=%s" % args.subset)
    print("indexed_items=%d" % len(item_index))
    print("sft_examples=%d" % sft_count)
    print("dpo_pairs=%d" % dpo_count)
    print("sft_jsonl=%s" % sft_path)
    print("dpo_jsonl=%s" % dpo_path)
    print("manifest=%s" % manifest_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
