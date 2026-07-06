#!/usr/bin/env python3
"""Upload the demo dataset and train the edge model directly on the SS928 board."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> None:
    print(" ".join(command))
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        raise RuntimeError("command failed: %s" % " ".join(command))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(ROOT / "demo_dataset"))
    parser.add_argument("--board", default="hieulerpi")
    parser.add_argument("--remote-root", default="/root/workspace/smart-wardrobe")
    parser.add_argument("--restart", action="store_true", default=True)
    args = parser.parse_args()

    dataset = Path(args.dataset)
    if not (dataset / "labels.csv").exists():
        raise SystemExit("labels.csv not found in %s" % dataset)

    remote_lab = args.remote_root.rstrip("/") + "/vision_lab"
    remote_dataset = remote_lab + "/" + dataset.name
    run(["ssh", args.board, "mkdir -p %s" % remote_lab])
    run(["scp", str(ROOT / "train_demo_model.py"), str(ROOT / "demo_wardrobe.json"), "%s:%s/" % (args.board, remote_lab)])
    run(["ssh", args.board, "rm -rf %s" % remote_dataset])
    run(["scp", "-r", str(dataset), "%s:%s/" % (args.board, remote_lab)])
    train_cmd = (
        "cd %s && python3 vision_lab/train_demo_model.py "
        "--dataset vision_lab/%s --wardrobe vision_lab/demo_wardrobe.json --out data/vision_model.json"
    ) % (args.remote_root, dataset.name)
    if args.restart:
        train_cmd += " && systemctl restart smart-wardrobe.service && sleep 2 && systemctl is-active smart-wardrobe.service"
    run(["ssh", args.board, train_cmd])
    print("board_model=%s/data/vision_model.json" % args.remote_root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
