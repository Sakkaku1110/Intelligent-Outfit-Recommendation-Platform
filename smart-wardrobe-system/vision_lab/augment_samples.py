#!/usr/bin/env python3
"""Create blurred, dark, and noisy copies of labeled samples."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:
        raise SystemExit("OpenCV/numpy required for augmentation: %s" % exc)

    labels_path = Path(args.labels).resolve()
    source_root = labels_path.parent
    out_root = Path(args.out).resolve() if args.out else source_root.with_name(source_root.name + "_augmented")
    image_out = out_root / "images"
    image_out.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(labels_path.open("r", encoding="utf-8-sig")))
    out_rows = []
    variants = {
        "orig": lambda img: img,
        "blur": lambda img: cv2.GaussianBlur(img, (9, 9), 0),
        "dark": lambda img: cv2.convertScaleAbs(img, alpha=0.62, beta=-12),
        "noisy": lambda img: cv2.add(
            img,
            np.random.normal(0, 13, img.shape).astype("int16"),
            dtype=cv2.CV_8U,
        ),
        "dark_blur": lambda img: cv2.convertScaleAbs(cv2.GaussianBlur(img, (7, 7), 0), alpha=0.66, beta=-10),
    }

    for row in rows:
        src = source_root / row["image_path"]
        image = cv2.imread(str(src))
        if image is None:
            print("skip unreadable", src)
            continue
        for name, fn in variants.items():
            target = image_out / ("%s_%s%s" % (src.stem, name, src.suffix or ".jpg"))
            cv2.imwrite(str(target), fn(image))
            out_row = dict(row)
            out_row["image_path"] = str(target.relative_to(out_root)).replace("\\", "/")
            out_row["variant"] = name
            out_rows.append(out_row)

    labels_out = out_root / "labels.csv"
    fieldnames = list(out_rows[0].keys()) if out_rows else ["image_path", "variant"]
    with labels_out.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print("augmented=%d" % len(out_rows))
    print("labels=%s" % labels_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
