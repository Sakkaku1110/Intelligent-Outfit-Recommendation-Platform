#!/usr/bin/env python3
"""Evaluate current ImageAnalyzer against a labeled sample CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "board"))

from app.core import ImageAnalyzer, color_family, normalize_category  # noqa: E402


def norm_text(value: str) -> str:
    return str(value or "").strip().lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--no-focus-viewfinder", action="store_true")
    args = parser.parse_args()

    labels_path = Path(args.labels).resolve()
    image_root = labels_path.parent
    report_path = Path(args.report).resolve() if args.report else labels_path.with_name("vision_report.csv")
    focus_viewfinder = not args.no_focus_viewfinder
    analyzer = ImageAnalyzer()

    rows = list(csv.DictReader(labels_path.open("r", encoding="utf-8-sig")))
    results = []
    item_ok = 0
    category_ok = 0
    color_ok = 0
    confusion: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        image_path = image_root / row["image_path"]
        expected_category = normalize_category(row.get("category"))
        expected_color_family = color_family(row.get("color"))
        expected_label_id = norm_text(row.get("label_id", ""))
        analysis = analyzer.analyze(str(image_path), focus_viewfinder=focus_viewfinder)
        predicted_label_id = norm_text(analysis.get("item_id", ""))
        predicted_category = normalize_category(analysis.get("category"))
        predicted_color_family = color_family(analysis.get("color"))
        item_match = bool(expected_label_id) and predicted_label_id == expected_label_id
        category_match = predicted_category == expected_category
        color_match = predicted_color_family == expected_color_family
        item_ok += int(item_match)
        category_ok += int(category_match)
        color_ok += int(color_match)
        confusion[expected_category][predicted_category] += 1
        results.append(
            {
                **row,
                "pred_label_id": predicted_label_id,
                "pred_category": predicted_category,
                "pred_color": analysis.get("color", ""),
                "pred_color_family": predicted_color_family,
                "pred_material": analysis.get("material", ""),
                "category_confidence": analysis.get("confidence", {}).get("category", 0),
                "color_confidence": analysis.get("confidence", {}).get("color", 0),
                "material_confidence": analysis.get("confidence", {}).get("material", 0),
                "item_match": item_match,
                "category_match": category_match,
                "color_family_match": color_match,
            }
        )

    total = max(1, len(results))
    print("samples=%d" % len(results))
    print("item_accuracy=%.2f%%" % (item_ok * 100 / total))
    print("category_accuracy=%.2f%%" % (category_ok * 100 / total))
    print("color_family_accuracy=%.2f%%" % (color_ok * 100 / total))
    print("confusion:")
    for expected, counter in sorted(confusion.items()):
        detail = ", ".join("%s=%d" % (pred, count) for pred, count in sorted(counter.items()))
        print("  %s -> %s" % (expected, detail))

    fieldnames = list(results[0].keys()) if results else []
    with report_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print("report=%s" % report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
