import argparse
import sys
from pathlib import Path

import torch
from sklearn.metrics import accuracy_score, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outfit_recommender.data import (  # noqa: E402
    OutfitCompatibilityDataset,
    collate_outfits,
)
from outfit_recommender.model import OutfitCompatibilityModel  # noqa: E402
from outfit_recommender.utils import (  # noqa: E402
    get_device,
    save_checkpoint,
    seed_everything,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train outfit compatibility model.")
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
        "--checkpoint-dir", type=Path, default=Path("checkpoints")
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--max-items", type=int, default=8)
    parser.add_argument("--max-train-samples", type=int, default=None)
    parser.add_argument("--max-validation-samples", type=int, default=None)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument("--freeze-backbone", action="store_true")
    return parser.parse_args()


def move_batch(batch: dict, device: torch.device) -> dict:
    return {
        key: value.to(device, non_blocking=True)
        if isinstance(value, torch.Tensor)
        else value
        for key, value in batch.items()
    }


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    labels = []
    probabilities = []

    progress = tqdm(loader, desc="train" if training else "validation")
    for batch in progress:
        batch = move_batch(batch, device)
        with torch.set_grad_enabled(training):
            logits = model(batch["images"], batch["categories"], batch["mask"])
            loss = criterion(logits, batch["labels"])
            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                optimizer.step()

        total_loss += loss.item() * batch["labels"].shape[0]
        labels.extend(batch["labels"].detach().cpu().tolist())
        probabilities.extend(torch.sigmoid(logits).detach().cpu().tolist())
        progress.set_postfix(loss=f"{loss.item():.4f}")

    predictions = [probability >= 0.5 for probability in probabilities]
    metrics = {
        "loss": total_loss / len(loader.dataset),
        "accuracy": accuracy_score(labels, predictions),
    }
    if len(set(labels)) > 1:
        metrics["auc"] = roc_auc_score(labels, probabilities)
    else:
        metrics["auc"] = float("nan")
    return metrics


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    device = get_device(args.device)
    print(f"Using device: {device}")

    train_dataset = OutfitCompatibilityDataset(
        args.dataset_dir,
        split="train",
        image_dir=args.image_dir,
        image_size=args.image_size,
        max_samples=args.max_train_samples,
        max_items=args.max_items,
        training=True,
    )
    validation_dataset = OutfitCompatibilityDataset(
        args.dataset_dir,
        split="validation",
        image_dir=args.image_dir,
        image_size=args.image_size,
        max_samples=args.max_validation_samples,
        max_items=args.max_items,
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        collate_fn=collate_outfits,
        pin_memory=device.type == "cuda",
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        collate_fn=collate_outfits,
        pin_memory=device.type == "cuda",
    )

    model = OutfitCompatibilityModel(
        pretrained_backbone=not args.no_pretrained,
        freeze_backbone=args.freeze_backbone,
    ).to(device)
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    criterion = nn.BCEWithLogitsLoss()
    best_auc = float("-inf")

    for epoch in range(1, args.epochs + 1):
        train_metrics = run_epoch(
            model, train_loader, criterion, device, optimizer=optimizer
        )
        validation_metrics = run_epoch(
            model, validation_loader, criterion, device
        )
        print(
            f"Epoch {epoch}: "
            f"train_loss={train_metrics['loss']:.4f}, "
            f"train_auc={train_metrics['auc']:.4f}, "
            f"val_loss={validation_metrics['loss']:.4f}, "
            f"val_auc={validation_metrics['auc']:.4f}"
        )

        save_checkpoint(
            args.checkpoint_dir / "last.pt",
            model,
            optimizer,
            epoch,
            validation_metrics,
            model.config(),
        )
        if epoch == 1 or validation_metrics["auc"] > best_auc:
            best_auc = validation_metrics["auc"]
            save_checkpoint(
                args.checkpoint_dir / "best.pt",
                model,
                optimizer,
                epoch,
                validation_metrics,
                model.config(),
            )
            print(f"Saved new best checkpoint with AUC={best_auc:.4f}")


if __name__ == "__main__":
    main()
