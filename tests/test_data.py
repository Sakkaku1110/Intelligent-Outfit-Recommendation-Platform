import json
from pathlib import Path

import torch
from PIL import Image

from outfit_recommender.data import (
    build_item_lookup,
    center_on_white_square,
    collate_outfits,
    load_compatibility_samples,
    normalize_item_image,
)


def test_load_compatibility_samples(tmp_path: Path) -> None:
    outfits_path = tmp_path / "train.json"
    outfits_path.write_text(
        json.dumps(
            [
                {
                    "set_id": "set1",
                    "items": [
                        {"item_id": "top1", "index": 1},
                        {"item_id": "shoe1", "index": 2},
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    compatibility_path = tmp_path / "compatibility_train.txt"
    compatibility_path.write_text("1 set1_1 set1_2\n", encoding="utf-8")

    lookup = build_item_lookup(outfits_path)
    samples = load_compatibility_samples(compatibility_path, lookup)

    assert samples[0].label == 1.0
    assert samples[0].item_ids == ("top1", "shoe1")


def test_collate_outfits_pads_variable_length() -> None:
    batch = [
        {
            "images": torch.ones(2, 3, 8, 8),
            "categories": torch.tensor([1, 5]),
            "label": torch.tensor(1.0),
            "item_ids": ("a", "b"),
        },
        {
            "images": torch.ones(3, 3, 8, 8),
            "categories": torch.tensor([1, 2, 5]),
            "label": torch.tensor(0.0),
            "item_ids": ("c", "d", "e"),
        },
    ]

    result = collate_outfits(batch)

    assert result["images"].shape == (2, 3, 3, 8, 8)
    assert result["mask"].tolist() == [[True, True, False], [True, True, True]]
    assert result["labels"].tolist() == [1.0, 0.0]


def test_sample_limit_balances_labels(tmp_path: Path) -> None:
    outfits_path = tmp_path / "train.json"
    outfits_path.write_text(
        json.dumps(
            [
                {
                    "set_id": "set1",
                    "items": [{"item_id": "item1", "index": 1}],
                }
            ]
        ),
        encoding="utf-8",
    )
    compatibility_path = tmp_path / "compatibility_train.txt"
    compatibility_path.write_text(
        "1 set1_1\n1 set1_1\n0 set1_1\n0 set1_1\n",
        encoding="utf-8",
    )

    samples = load_compatibility_samples(
        compatibility_path,
        build_item_lookup(outfits_path),
        max_samples=2,
    )

    assert {sample.label for sample in samples} == {0.0, 1.0}


def test_normalize_item_image_crops_subject_to_white_square() -> None:
    image = Image.new("RGB", (100, 80), (40, 40, 40))
    for x in range(30, 70):
        for y in range(20, 60):
            image.putpixel((x, y), (220, 30, 30))

    normalized = normalize_item_image(image, padding_ratio=0.0)

    assert normalized.size == (40, 40)
    assert normalized.getpixel((20, 20)) == (220, 30, 30)


def test_center_on_white_square_uses_alpha_mask() -> None:
    image = Image.new("RGBA", (80, 60), (0, 0, 0, 0))
    for x in range(20, 50):
        for y in range(10, 50):
            image.putpixel((x, y), (30, 120, 220, 255))

    normalized = center_on_white_square(image, padding_ratio=0.0)

    assert normalized.mode == "RGB"
    assert normalized.size == (40, 40)
    assert normalized.getpixel((15, 20)) == (30, 120, 220)
