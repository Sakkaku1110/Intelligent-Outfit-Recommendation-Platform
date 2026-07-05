#!/usr/bin/env python3
"""Download reviewed wardrobe images from the board and build labels.csv."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


def curl_bytes(url: str) -> bytes | None:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        return None
    return subprocess.check_output([curl, "-fsSL", "--max-time", "12", url])


def fetch_json(url: str) -> dict:
    body = curl_bytes(url)
    if body is not None:
        return json.loads(body.decode("utf-8"))
    with urllib.request.urlopen(url, timeout=20) as response:
        length = int(response.headers.get("Content-Length") or "0")
        body = response.read(length) if length else response.read()
        return json.loads(body.decode("utf-8"))


def download(url: str, target: Path) -> None:
    body = curl_bytes(url)
    if body is not None:
        target.write_bytes(body)
        return
    with urllib.request.urlopen(url, timeout=8) as response:
        length = int(response.headers.get("Content-Length") or "0")
        target.write_bytes(response.read(length) if length else response.read())


def safe_name(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value.strip(), flags=re.UNICODE)
    return value[:48] or "item"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://192.168.137.2")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "samples"))
    args = parser.parse_args()

    base = args.base.rstrip("/")
    out_dir = Path(args.out)
    image_dir = out_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    labels_path = out_dir / "labels.csv"

    data = fetch_json(base + "/api/clothes")
    rows = []
    for item in data.get("items", []):
        image_url = item.get("image_url") or ""
        if not image_url:
            continue
        full_url = urllib.parse.urljoin(base + "/", image_url.lstrip("/"))
        suffix = Path(urllib.parse.urlparse(image_url).path).suffix or ".jpg"
        filename = "%s_%s_%s%s" % (
            item.get("id"),
            safe_name(item.get("category") or "unknown"),
            safe_name(item.get("name") or "item"),
            suffix,
        )
        target = image_dir / filename
        try:
            download(full_url, target)
        except Exception as exc:
            print("skip %s: %s" % (full_url, exc))
            continue
        print("downloaded", filename)
        rows.append(
            {
                "image_path": str(target.relative_to(out_dir)).replace("\\", "/"),
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "category": item.get("category", ""),
                "color": item.get("color", ""),
                "material": item.get("material", ""),
            }
        )

    with labels_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file, fieldnames=["image_path", "id", "name", "category", "color", "material"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print("downloaded=%d" % len(rows))
    print("labels=%s" % labels_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
