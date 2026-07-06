#!/usr/bin/env python3
"""Create a cloud-cropped copy of a dataset before training."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
BOARD_ROOT = PROJECT_ROOT / "board"
sys.path.insert(0, str(BOARD_ROOT))

from app.core import CloudPreprocessor  # noqa: E402


FIELDS = ["sample_id", "image_path", "label_id", "name", "category", "color", "material", "created_at"]


def copy_or_preprocess(source: Path, target: Path, preprocessor: CloudPreprocessor, fallback_copy: bool) -> tuple[bool, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = preprocessor.preprocess(str(source), image_url="")
    if result.get("ok") and result.get("image_path"):
        shutil.copy2(result["image_path"], target)
        return True, "cloud"
    if fallback_copy:
        shutil.copy2(source, target)
        return True, "fallback"
    return False, str(result.get("message") or result.get("reason") or "cloud preprocessing failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(ROOT / "demo_dataset"))
    parser.add_argument("--out", default=str(ROOT / "demo_dataset_cloud"))
    parser.add_argument("--fallback-copy", action="store_true", help="Copy original image when cloud preprocessing fails.")
    args = parser.parse_args()

    dataset = Path(args.dataset)
    output = Path(args.out)
    labels_path = dataset / "labels.csv"
    if not labels_path.exists():
        raise SystemExit("labels.csv not found: %s" % labels_path)

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    preprocessor = CloudPreprocessor(output / "_cloud_tmp")
    rows = list(csv.DictReader(labels_path.open("r", encoding="utf-8-sig")))
    new_rows = []
    ok_count = 0
    fail_count = 0
    for row in rows:
        source = dataset / row["image_path"]
        target = output / row["image_path"]
        ok, mode = copy_or_preprocess(source, target, preprocessor, args.fallback_copy)
        if ok:
            ok_count += 1
            new_rows.append({field: row.get(field, "") for field in FIELDS})
            print("ok %s %s" % (mode, row["image_path"]))
        else:
            fail_count += 1
            print("skip %s %s" % (row["image_path"], mode))

    labels_out = output / "labels.csv"
    with labels_out.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(new_rows)
    shutil.copy2(ROOT / "demo_wardrobe.json", output / "demo_wardrobe.json")
    print("output=%s" % output)
    print("saved=%d failed=%d" % (ok_count, fail_count))
    return 0 if ok_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
