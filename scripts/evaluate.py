import argparse
import sys
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outfit_recommender.data import (  # noqa: E402
    OutfitCompatibilityDataset,
    collate_outfits,
)
from outfit_recommender.model import OutfitCompatibilityModel  # noqa: E402
from outfit_recommender.utils import get_device  # noqa: E402
from train import run_epoch  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a trained checkpoint.")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/polyvore-outfits"),
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=Path("data/polyvore-outfits/images"),
    )
    parser.add_argument(
        "--checkpoint", type=Path, default=Path("checkpoints/best.pt")
    )
    parser.add_argument(
        "--split", choices=("validation", "test"), default="test"
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--max-items", type=int, default=8)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = get_device(args.device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model = OutfitCompatibilityModel(**checkpoint["model_config"]).to(device)
    model.load_state_dict(checkpoint["model_state"])

    dataset = OutfitCompatibilityDataset(
        args.dataset_dir,
        split=args.split,
        image_dir=args.image_dir,
        image_size=args.image_size,
        max_samples=args.max_samples,
        max_items=args.max_items,
    )
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        collate_fn=collate_outfits,
        pin_memory=device.type == "cuda",
    )
    metrics = run_epoch(model, loader, nn.BCEWithLogitsLoss(), device)
    print(
        f"{args.split}: loss={metrics['loss']:.4f}, "
        f"accuracy={metrics['accuracy']:.4f}, auc={metrics['auc']:.4f}"
    )


if __name__ == "__main__":
    main()
