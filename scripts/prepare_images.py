import argparse
import sys
from pathlib import Path

import pyarrow.parquet as pq
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outfit_recommender.data import (  # noqa: E402
    build_item_lookup,
    load_compatibility_samples,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Polyvore images from Parquet into a training cache."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/polyvore-outfits"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/polyvore-outfits/images"),
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        choices=("train", "validation", "test"),
        default=("train", "validation"),
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Only extract images needed by the first N compatibility samples.",
    )
    parser.add_argument("--max-items", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=512)
    return parser.parse_args()


def required_item_ids(
    dataset_dir: Path,
    split: str,
    max_samples: int | None,
    max_items: int,
) -> set[str]:
    file_split = "valid" if split == "validation" else split
    split_dir = dataset_dir / "disjoint"
    lookup = build_item_lookup(split_dir / f"{file_split}.json")
    samples = load_compatibility_samples(
        split_dir / f"compatibility_{file_split}.txt",
        lookup,
        max_samples=max_samples,
        max_items=max_items,
    )
    return {item_id for sample in samples for item_id in sample.item_ids}


def extract_split(
    parquet_path: Path,
    output_dir: Path,
    wanted_ids: set[str],
    batch_size: int,
) -> tuple[int, set[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    missing_ids = {
        item_id
        for item_id in wanted_ids
        if not (output_dir / f"{item_id}.jpg").is_file()
    }
    if not missing_ids:
        return 0, set()

    parquet_file = pq.ParquetFile(parquet_path)
    extracted = 0
    progress = tqdm(
        total=parquet_file.metadata.num_rows,
        desc=f"Scanning {parquet_path.name}",
        unit="item",
    )
    for batch in parquet_file.iter_batches(
        batch_size=batch_size, columns=("item_id", "image")
    ):
        rows = batch.to_pylist()
        progress.update(len(rows))
        for row in rows:
            item_id = row["item_id"]
            if item_id not in missing_ids:
                continue
            image_bytes = row["image"]["bytes"]
            if image_bytes:
                (output_dir / f"{item_id}.jpg").write_bytes(image_bytes)
                missing_ids.remove(item_id)
                extracted += 1
        if not missing_ids:
            break
    progress.close()
    return extracted, missing_ids


def main() -> None:
    args = parse_args()
    dataset_dir = args.dataset_dir.resolve()
    output_dir = args.output_dir.resolve()

    total_extracted = 0
    all_missing = set()
    for split in args.splits:
        wanted_ids = required_item_ids(
            dataset_dir, split, args.max_samples, args.max_items
        )
        parquet_path = dataset_dir / "data" / "disjoint" / f"{split}.parquet"
        extracted, missing = extract_split(
            parquet_path, output_dir, wanted_ids, args.batch_size
        )
        total_extracted += extracted
        all_missing.update(missing)
        print(
            f"{split}: required={len(wanted_ids):,}, "
            f"extracted={extracted:,}, missing={len(missing):,}"
        )

    if all_missing:
        raise RuntimeError(
            f"{len(all_missing)} required images were not found in the Parquet files."
        )
    print(f"Image preparation complete. New files: {total_extracted:,}")


if __name__ == "__main__":
    main()

