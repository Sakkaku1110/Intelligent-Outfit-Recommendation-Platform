import json
import os
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable, Literal

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from .constants import CATEGORY_TO_INDEX


@dataclass(frozen=True)
class CompatibilitySample:
    label: float
    item_ids: tuple[str, ...]


ImagePreprocessMode = Literal["none", "simple", "segmentation", "auto"]
SegmentationModel = Literal["u2netp", "u2net"]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def ensure_preprocess_cache_dirs() -> None:
    numba_cache_dir = PROJECT_ROOT / ".cache" / "numba"
    u2net_home = PROJECT_ROOT / ".cache" / "u2net"
    numba_cache_dir.mkdir(parents=True, exist_ok=True)
    u2net_home.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(numba_cache_dir))
    os.environ.setdefault("U2NET_HOME", str(u2net_home))


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


def center_on_white_square(
    image: Image.Image,
    mask: np.ndarray | None = None,
    padding_ratio: float = 0.12,
) -> Image.Image:
    image = image.convert("RGBA")
    if mask is None:
        mask = np.asarray(image.getchannel("A")) > 10
    foreground_ratio = mask.mean()
    if foreground_ratio < 0.01 or foreground_ratio > 0.95:
        return image.convert("RGB")

    rows, columns = np.where(mask)
    left, right = columns.min(), columns.max() + 1
    top, bottom = rows.min(), rows.max() + 1
    box_width = right - left
    box_height = bottom - top
    padding = int(max(box_width, box_height) * padding_ratio)
    left = max(left - padding, 0)
    top = max(top - padding, 0)
    right = min(right + padding, image.width)
    bottom = min(bottom + padding, image.height)

    cropped = image.crop((left, top, right, bottom))
    canvas_size = max(cropped.size)
    transparent_canvas = Image.new(
        "RGBA", (canvas_size, canvas_size), (255, 255, 255, 0)
    )
    offset = (
        (canvas_size - cropped.width) // 2,
        (canvas_size - cropped.height) // 2,
    )
    transparent_canvas.paste(cropped, offset, cropped.getchannel("A"))
    white_canvas = Image.new("RGB", transparent_canvas.size, (255, 255, 255))
    white_canvas.paste(transparent_canvas, mask=transparent_canvas.getchannel("A"))
    return white_canvas


def normalize_item_image(
    image: Image.Image,
    padding_ratio: float = 0.12,
    background_threshold: float = 30.0,
) -> Image.Image:
    image = image.convert("RGB")
    pixels = np.asarray(image, dtype=np.int16)
    border_pixels = np.concatenate(
        (
            pixels[0, :, :],
            pixels[-1, :, :],
            pixels[:, 0, :],
            pixels[:, -1, :],
        ),
        axis=0,
    )
    background_color = np.median(border_pixels, axis=0)
    color_distance = np.linalg.norm(pixels - background_color, axis=2)
    foreground_mask = color_distance > background_threshold
    return center_on_white_square(image, foreground_mask, padding_ratio)


def remove_item_background(
    image: Image.Image,
    session=None,
    padding_ratio: float = 0.12,
) -> Image.Image:
    ensure_preprocess_cache_dirs()
    try:
        from rembg import remove
    except ImportError as error:
        raise RuntimeError(
            "Image segmentation preprocessing requires rembg. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from error

    result = remove(image.convert("RGB"), session=session)
    if isinstance(result, bytes):
        result = Image.open(BytesIO(result))
    return center_on_white_square(result.convert("RGBA"), padding_ratio=padding_ratio)


class ItemImagePreprocessor:
    def __init__(
        self,
        mode: ImagePreprocessMode,
        segmentation_model: SegmentationModel = "u2netp",
    ) -> None:
        self.mode = mode
        self.segmentation_model = segmentation_model
        self._session = None
        self._segmentation_failed = False

    def __call__(self, image: Image.Image) -> Image.Image:
        image = image.convert("RGB")
        if self.mode == "none":
            return image
        if self.mode == "simple":
            return normalize_item_image(image)
        if self.mode == "auto" and self._segmentation_failed:
            return normalize_item_image(image)

        try:
            ensure_preprocess_cache_dirs()
            if self._session is None:
                try:
                    from rembg import new_session
                except ImportError as error:
                    raise RuntimeError(
                        "Image segmentation preprocessing requires rembg. "
                        "Install dependencies with: pip install -r requirements.txt"
                    ) from error

                self._session = new_session(self.segmentation_model)
            return remove_item_background(image, session=self._session)
        except Exception as error:
            if self.mode == "auto":
                self._segmentation_failed = True
                warnings.warn(
                    "Segmentation preprocessing is unavailable; falling back "
                    "to simple image cropping. Install rembg and allow its "
                    "model download to enable model-based background removal.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return normalize_item_image(image)
            raise


def default_image_transform(
    image_size: int = 224,
    training: bool = False,
    preprocess: bool = False,
    preprocess_mode: ImagePreprocessMode | None = None,
    segmentation_model: SegmentationModel = "u2netp",
):
    operations: list[Callable] = []
    if preprocess_mode is None:
        preprocess_mode = "simple" if preprocess else "none"
    if preprocess_mode != "none":
        operations.append(ItemImagePreprocessor(preprocess_mode, segmentation_model))
    operations.append(transforms.Resize((image_size, image_size)))
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
