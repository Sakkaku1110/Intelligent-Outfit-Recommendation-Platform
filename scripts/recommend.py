import argparse
import itertools
import json
import sys
from pathlib import Path

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outfit_recommender.constants import CATEGORY_TO_INDEX  # noqa: E402
from outfit_recommender.data import default_image_transform  # noqa: E402
from outfit_recommender.model import OutfitCompatibilityModel  # noqa: E402
from outfit_recommender.utils import get_device  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank outfit combinations from a wardrobe manifest."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--checkpoint", type=Path, default=Path("checkpoints/best.pt")
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-candidates", type=int, default=5000)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--preprocess-mode",
        choices=("segmentation", "auto", "simple", "none"),
        default="auto",
        help=(
            "Image preprocessing mode. auto uses rembg segmentation when "
            "available and falls back to simple cropping, segmentation "
            "requires rembg, simple uses border-color cropping, and none "
            "disables preprocessing."
        ),
    )
    parser.add_argument(
        "--segmentation-model",
        choices=("u2netp", "u2net"),
        default="u2netp",
        help=(
            "rembg segmentation model. u2netp is smaller and faster; "
            "u2net is larger and usually more accurate."
        ),
    )
    parser.add_argument(
        "--no-preprocess-images",
        action="store_true",
        help="Deprecated alias for --preprocess-mode none.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    items = data["items"] if isinstance(data, dict) else data
    for item in items:
        if item["category"] not in CATEGORY_TO_INDEX:
            raise ValueError(f"Unsupported category: {item['category']}")
        image_path = Path(item["image"])
        if not image_path.is_absolute():
            image_path = path.parent / image_path
        item["image"] = image_path
    return items


def generate_candidates(items: list[dict], maximum: int) -> list[tuple[dict, ...]]:
    by_category = {}
    for item in items:
        by_category.setdefault(item["category"], []).append(item)

    candidates = []
    outerwear_options = [None, *by_category.get("outerwear", [])]
    for top, bottom, shoes, outerwear in itertools.product(
        by_category.get("tops", []),
        by_category.get("bottoms", []),
        by_category.get("shoes", []),
        outerwear_options,
    ):
        candidates.append(
            tuple(item for item in (top, bottom, shoes, outerwear) if item)
        )
        if len(candidates) >= maximum:
            return candidates

    for dress, shoes, outerwear in itertools.product(
        by_category.get("all-body", []),
        by_category.get("shoes", []),
        outerwear_options,
    ):
        candidates.append(
            tuple(item for item in (dress, shoes, outerwear) if item)
        )
        if len(candidates) >= maximum:
            break
    return candidates


def load_item_tensor(item: dict, transform) -> torch.Tensor:
    with Image.open(item["image"]) as image:
        return transform(image.convert("RGB"))


def score_candidates(
    candidates: list[tuple[dict, ...]],
    model: OutfitCompatibilityModel,
    device: torch.device,
    image_size: int,
    batch_size: int,
    preprocess_mode: str,
    segmentation_model: str,
) -> list[tuple[float, tuple[dict, ...]]]:
    transform = default_image_transform(
        image_size,
        preprocess_mode=preprocess_mode,
        segmentation_model=segmentation_model,
    )
    image_cache = {}
    results = []

    for start in range(0, len(candidates), batch_size):
        candidate_batch = candidates[start:start + batch_size]
        max_items = max(len(candidate) for candidate in candidate_batch)
        images = torch.zeros(
            len(candidate_batch), max_items, 3, image_size, image_size
        )
        categories = torch.zeros(
            len(candidate_batch), max_items, dtype=torch.long
        )
        mask = torch.zeros(len(candidate_batch), max_items, dtype=torch.bool)

        for batch_index, candidate in enumerate(candidate_batch):
            for item_index, item in enumerate(candidate):
                cache_key = str(item["image"])
                if cache_key not in image_cache:
                    image_cache[cache_key] = load_item_tensor(item, transform)
                images[batch_index, item_index] = image_cache[cache_key]
                categories[batch_index, item_index] = CATEGORY_TO_INDEX[
                    item["category"]
                ]
                mask[batch_index, item_index] = True

        with torch.inference_mode():
            logits = model(
                images.to(device),
                categories.to(device),
                mask.to(device),
            )
            scores = torch.sigmoid(logits).cpu().tolist()
        results.extend(zip(scores, candidate_batch))
    return results


def main() -> None:
    args = parse_args()
    device = get_device(args.device)
    preprocess_mode = "none" if args.no_preprocess_images else args.preprocess_mode
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model = OutfitCompatibilityModel(**checkpoint["model_config"]).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    items = load_manifest(args.manifest)
    candidates = generate_candidates(items, args.max_candidates)
    if not candidates:
        raise ValueError(
            "No outfits could be generated. Provide tops + bottoms + shoes, "
            "or all-body + shoes."
        )
    ranked = sorted(
        score_candidates(
            candidates,
            model,
            device,
            args.image_size,
            args.batch_size,
            preprocess_mode,
            args.segmentation_model,
        ),
        key=lambda result: result[0],
        reverse=True,
    )

    print(f"Generated {len(candidates):,} candidates on {device}.")
    for rank, (score, candidate) in enumerate(ranked[: args.top_k], start=1):
        names = ", ".join(item.get("name", item["id"]) for item in candidate)
        print(f"{rank}. score={score:.4f} | {names}")


if __name__ == "__main__":
    main()
