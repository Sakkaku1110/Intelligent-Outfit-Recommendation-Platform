#!/usr/bin/env python3
"""Evaluate ImageAnalyzer against the board SQLite wardrobe database."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import ImageAnalyzer, color_family, normalize_category  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(ROOT / "data" / "wardrobe.db"))
    parser.add_argument("--no-focus-viewfinder", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    analyzer = ImageAnalyzer()
    focus_viewfinder = not args.no_focus_viewfinder
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, name, category, color, material, image_path
            FROM clothes
            WHERE image_path != ''
            ORDER BY id
            """
        ).fetchall()

    total = 0
    category_ok = 0
    color_ok = 0
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        image_path = Path(row["image_path"])
        if not image_path.exists():
            continue
        total += 1
        expected_category = normalize_category(row["category"])
        expected_color = color_family(row["color"])
        analysis = analyzer.analyze(str(image_path), focus_viewfinder=focus_viewfinder)
        predicted_category = normalize_category(analysis.get("category"))
        predicted_color = color_family(analysis.get("color"))
        category_ok += int(expected_category == predicted_category)
        color_ok += int(expected_color == predicted_color)
        confusion[expected_category][predicted_category] += 1
        confidence = analysis.get("confidence") or {}
        print(
            "#%s %-18s expected=%s/%s predicted=%s/%s conf=%.3f/%.3f"
            % (
                row["id"],
                row["name"][:18],
                expected_category,
                expected_color,
                predicted_category,
                predicted_color,
                float(confidence.get("category") or 0),
                float(confidence.get("color") or 0),
            )
        )

    denom = max(1, total)
    print("samples=%d" % total)
    print("category_accuracy=%.2f%%" % (category_ok * 100 / denom))
    print("color_family_accuracy=%.2f%%" % (color_ok * 100 / denom))
    print("confusion:")
    for expected, counter in sorted(confusion.items()):
        detail = ", ".join("%s=%d" % (pred, count) for pred, count in sorted(counter.items()))
        print("  %s -> %s" % (expected, detail))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
