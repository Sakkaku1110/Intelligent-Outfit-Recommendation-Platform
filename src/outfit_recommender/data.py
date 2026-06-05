import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from .constants import CATEGORY_TO_INDEX


@dataclass(frozen=True)
class CompatibilitySample:
    label: float
    item_ids: tuple[str, ...]


def build_item_lookup(outfits_path: Path) -> dict[str, str]:
    with outfits_path.open(encoding="utf-8") as file:
        outfits = json.load(file)

    lookup = {}
    for outfit in outfits:
        set_id = outfit["set_id"]
        for item in outfit["items"]:
            lookup[f"{set_id}_{item['index']}"] = item["item_id"]
    return lookup


def load_compatibility_samples(
    compatibility_path: Path,
    item_lookup: dict[str, str],
    max_samples: int | None = None,
    max_items: int = 8,
) -> list[CompatibilitySample]:
    samples = []
    with compatibility_path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            parts = line.split()
            if not parts:
                continue
            try:
                item_ids = tuple(item_lookup[token] for token in parts[1:max_items + 1])
            except KeyError as error:
                raise KeyError(
                    f"Unknown outfit token {error.args[0]!r} at "
                    f"{compatibility_path}:{line_number}"
                ) from error
            samples.append(CompatibilitySample(float(parts[0]), item_ids))
    if max_samples is not None and len(samples) > max_samples:
        positive = [sample for sample in samples if sample.label == 1.0]
        negative = [sample for sample in samples if sample.label == 0.0]
        positive_count = min((max_samples + 1) // 2, len(positive))
        negative_count = min(max_samples // 2, len(negative))
        selected = positive[:positive_count] + negative[:negative_count]
        if len(selected) < max_samples:
            selected_ids = {id(sample) for sample in selected}
            remainder = [
                sample for sample in samples if id(sample) not in selected_ids
            ]
            selected.extend(remainder[: max_samples - len(selected)])
        samples = selected
    return samples


def default_image_transform(image_size: int = 224, training: bool = False):
    operations: list[Callable] = [
        transforms.Resize((image_size, image_size)),
    ]
    if training:
        operations.extend(
            [
                transforms.RandomHorizontalFlip(),
                transforms.ColorJitter(brightness=0.1, contrast=0.1),
            ]
        )
    operations.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(
                mean=(0.485, 0.456, 0.406),
                std=(0.229, 0.224, 0.225),
            ),
        ]
    )
    return transforms.Compose(operations)


class OutfitCompatibilityDataset(Dataset):
    def __init__(
        self,
        dataset_dir: Path,
        split: str,
        image_dir: Path,
        image_size: int = 224,
        max_samples: int | None = None,
        max_items: int = 8,
        training: bool = False,
    ) -> None:
        split_file_name = "valid" if split == "validation" else split
        split_dir = dataset_dir / "disjoint"
        item_lookup = build_item_lookup(split_dir / f"{split_file_name}.json")
        self.samples = load_compatibility_samples(
            split_dir / f"compatibility_{split_file_name}.txt",
            item_lookup,
            max_samples=max_samples,
            max_items=max_items,
        )
        with (dataset_dir / "polyvore_item_metadata.json").open(
            encoding="utf-8"
        ) as file:
            self.metadata = json.load(file)
        self.image_dir = image_dir
        self.transform = default_image_transform(image_size, training=training)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict:
        sample = self.samples[index]
        images = []
        categories = []
        for item_id in sample.item_ids:
            image_path = self.image_dir / f"{item_id}.jpg"
            if not image_path.is_file():
                raise FileNotFoundError(
                    f"Missing {image_path}. Run scripts/prepare_images.py first."
                )
            with Image.open(image_path) as image:
                images.append(self.transform(image.convert("RGB")))
            category = self.metadata.get(item_id, {}).get(
                "semantic_category", "unknown"
            )
            categories.append(CATEGORY_TO_INDEX.get(category, 0))

        return {
            "images": torch.stack(images),
            "categories": torch.tensor(categories, dtype=torch.long),
            "label": torch.tensor(sample.label, dtype=torch.float32),
            "item_ids": sample.item_ids,
        }


def collate_outfits(batch: list[dict]) -> dict:
    batch_size = len(batch)
    max_items = max(sample["images"].shape[0] for sample in batch)
    channels, height, width = batch[0]["images"].shape[1:]

    images = torch.zeros(batch_size, max_items, channels, height, width)
    categories = torch.zeros(batch_size, max_items, dtype=torch.long)
    mask = torch.zeros(batch_size, max_items, dtype=torch.bool)

    for index, sample in enumerate(batch):
        item_count = sample["images"].shape[0]
        images[index, :item_count] = sample["images"]
        categories[index, :item_count] = sample["categories"]
        mask[index, :item_count] = True

    return {
        "images": images,
        "categories": categories,
        "mask": mask,
        "labels": torch.stack([sample["label"] for sample in batch]),
        "item_ids": [sample["item_ids"] for sample in batch],
    }
