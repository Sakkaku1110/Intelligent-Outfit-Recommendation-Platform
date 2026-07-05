#!/usr/bin/env python3
"""Train a small prototype matcher for the fixed demo wardrobe."""

from __future__ import annotations

import argparse
import csv
import json
import math
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageStat


warnings.filterwarnings("ignore", category=DeprecationWarning)


def feature_vector(image_path: Path) -> list[float]:
    image = Image.open(image_path).convert("RGB").resize((96, 96))
    stat = ImageStat.Stat(image)
    mean = [value / 255.0 for value in stat.mean]
    std = [value / 255.0 for value in stat.stddev]
    hsv = image.convert("HSV")
    hist = [0.0] * 8
    total = 0
    for h, s, v in hsv.getdata():
        if s <= 24 or v <= 24:
            continue
        index = min(7, int((h / 256.0) * 8))
        hist[index] += 1.0
        total += 1
    if total:
        hist = [value / total for value in hist]
    return [float(value) for value in mean + std + hist]


def mean_vector(vectors: list[list[float]]) -> list[float]:
    width = len(vectors[0])
    return [sum(vector[i] for vector in vectors) / len(vectors) for i in range(width)]


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(Path(__file__).resolve().parent / "demo_dataset"))
    parser.add_argument("--labels", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--wardrobe", default=str(Path(__file__).resolve().parent / "demo_wardrobe.json"))
    args = parser.parse_args()

    dataset = Path(args.dataset)
    labels_path = Path(args.labels) if args.labels else dataset / "labels.csv"
    out_path = Path(args.out) if args.out else dataset / "vision_model.json"
    wardrobe = json.loads(Path(args.wardrobe).read_text(encoding="utf-8"))
    wardrobe_by_id = {item["id"]: item for item in wardrobe["items"]}

    rows = list(csv.DictReader(labels_path.open("r", encoding="utf-8-sig")))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        label_id = row.get("label_id") or ""
        if label_id in wardrobe_by_id:
            groups[label_id].append(row)

    labels = []
    for label_id, samples in sorted(groups.items()):
        vectors = []
        used_samples = []
        for sample in samples:
            image_path = dataset / sample["image_path"]
            if not image_path.exists():
                continue
            vectors.append(feature_vector(image_path))
            used_samples.append(sample["image_path"])
        if not vectors:
            continue
        prototype = mean_vector(vectors)
        max_dist = max(distance(vector, prototype) for vector in vectors)
        item = dict(wardrobe_by_id[label_id])
        item["prototype"] = [round(value, 6) for value in prototype]
        item["samples"] = len(vectors)
        item["sample_paths"] = used_samples
        item["threshold"] = round(max(0.28, min(0.62, max_dist * 1.9 + 0.08)), 4)
        labels.append(item)

    model = {
        "version": 1,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature": "rgb_mean_std_hue8_96px",
        "threshold": 0.42,
        "labels": labels,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    print("labels=%d" % len(labels))
    print("model=%s" % out_path)
    for label in labels:
        print("%s samples=%s threshold=%s" % (label["id"], label["samples"], label["threshold"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
