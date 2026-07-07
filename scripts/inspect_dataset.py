import argparse
import csv
import json
from collections import Counter
from pathlib import Path


REQUIRED_PARQUET_FILES = (
    "data/disjoint/train.parquet",
    "data/disjoint/validation.parquet",
    "data/disjoint/test.parquet",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect the local Polyvore dataset.")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/polyvore-outfits"),
        help="Path to the downloaded Polyvore dataset.",
    )
    return parser.parse_args()


def load_categories(path: Path) -> dict[str, tuple[str, str]]:
    categories = {}
    with path.open(encoding="utf-8") as file:
        for category_id, category_name, semantic_category in csv.reader(file):
            categories[category_id] = (category_name, semantic_category)
    return categories


def main() -> None:
    args = parse_args()
    dataset_dir = args.dataset_dir.resolve()

    missing = [
        relative_path
        for relative_path in REQUIRED_PARQUET_FILES
        if not (dataset_dir / relative_path).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"Missing dataset files: {', '.join(missing)}")

    split_dir = dataset_dir / "disjoint"
    split_outfits = {}
    item_ids = set()
    outfit_lengths = Counter()

    for split_name in ("train", "valid", "test"):
        with (split_dir / f"{split_name}.json").open(encoding="utf-8") as file:
            outfits = json.load(file)
        split_outfits[split_name] = len(outfits)
        for outfit in outfits:
            outfit_lengths[len(outfit["items"])] += 1
            item_ids.update(item["item_id"] for item in outfit["items"])

    with (dataset_dir / "polyvore_item_metadata.json").open(
        encoding="utf-8"
    ) as file:
        metadata = json.load(file)
    categories = load_categories(dataset_dir / "categories.csv")

    semantic_categories = Counter()
    for item_id in item_ids:
        item = metadata.get(item_id, {})
        semantic_category = item.get("semantic_category") or "unknown"
        semantic_categories[semantic_category] += 1

    sample_id = next(iter(item_ids))
    sample = metadata[sample_id]
    category = categories.get(str(sample.get("category_id")), ("unknown", "unknown"))

    print(f"Dataset directory: {dataset_dir}")
    print(f"Disjoint outfits: {split_outfits}")
    print(f"Unique items referenced: {len(item_ids):,}")
    print(f"Outfit sizes: {dict(sorted(outfit_lengths.items()))}")
    print(f"Semantic categories: {dict(semantic_categories.most_common())}")
    print("\nSample item:")
    print(f"  item_id: {sample_id}")
    print(f"  title: {sample.get('title') or sample.get('url_name')}")
    print(f"  category: {category[0]}")
    print(f"  semantic category: {sample.get('semantic_category')}")
    print("\nDataset check passed.")


if __name__ == "__main__":
    main()
