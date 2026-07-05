#!/usr/bin/env python3
"""Deploy the trained demo vision model to the SS928 board."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=str(Path(__file__).resolve().parent / "demo_dataset" / "vision_model.json"))
    parser.add_argument("--host", default="hieulerpi")
    parser.add_argument("--remote", default="/root/workspace/smart-wardrobe/data/vision_model.json")
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()

    model = Path(args.model)
    if not model.exists():
        raise SystemExit("model not found: %s" % model)
    data = model.read_bytes()
    subprocess.run(["ssh", args.host, "mkdir -p /root/workspace/smart-wardrobe/data"], check=True)
    subprocess.run(["ssh", args.host, "cat > %s" % args.remote], input=data, check=True)
    if args.restart:
        subprocess.run(["ssh", args.host, "systemctl restart smart-wardrobe.service"], check=True)
    print("deployed=%s" % args.remote)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
