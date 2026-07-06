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

try:
    from PIL import Image, ImageStat, UnidentifiedImageError
except ImportError:  # Board-side training can run with OpenCV only.
    Image = None  # type: ignore
    ImageStat = None  # type: ignore

    class UnidentifiedImageError(OSError):
        pass


warnings.filterwarnings("ignore", category=DeprecationWarning)


def feature_vector(image_path: Path) -> list[float]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        image = cv2.imread(str(image_path))
        if image is None:
            raise UnidentifiedImageError(str(image_path))
        small = cv2.resize(image, (96, 96))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype("float32") / 255.0
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        pixels = rgb.reshape((-1, 3))
        mean = pixels.mean(axis=0).tolist()
        std = pixels.std(axis=0).tolist()
        h = hsv[:, :, 0].reshape(-1)
        s = hsv[:, :, 1].reshape(-1)
        v = hsv[:, :, 2].reshape(-1)
        valid = (s > 24) & (v > 24)
        if valid.any():
            hist = np.histogram(h[valid], bins=8, range=(0, 180))[0].astype("float32")
        else:
            hist = np.zeros(8, dtype="float32")
        hist = hist / max(1.0, float(hist.sum()))
        return [float(value) for value in mean + std + hist.tolist()]
    except ImportError:
        if Image is None or ImageStat is None:
            raise RuntimeError("Either OpenCV or Pillow is required to train the demo model.")
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
    skipped: list[str] = []
    for label_id, samples in sorted(groups.items()):
        vectors = []
        used_samples = []
        for sample in samples:
            image_path = dataset / sample["image_path"]
            if not image_path.exists():
                skipped.append("%s missing" % sample["image_path"])
                continue
            try:
                vectors.append(feature_vector(image_path))
                used_samples.append(sample["image_path"])
            except (OSError, UnidentifiedImageError) as exc:
                skipped.append("%s unreadable: %s" % (sample["image_path"], exc))
        if not vectors:
            continue
        prototype = mean_vector(vectors)
        max_dist = max(distance(vector, prototype) for vector in vectors)
        item = dict(wardrobe_by_id[label_id])
        item["prototype"] = [round(value, 6) for value in prototype]
        item["sample_vectors"] = [[round(value, 6) for value in vector] for vector in vectors]
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
    if skipped:
        print("skipped=%d" % len(skipped))
        for item in skipped[:20]:
            print("skip %s" % item)
        if len(skipped) > 20:
            print("skip ... %d more" % (len(skipped) - 20))
    for label in labels:
        print("%s samples=%s threshold=%s" % (label["id"], label["samples"], label["threshold"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
