#!/usr/bin/env python3
"""Utilities for preparing smart-wardrobe LLM training data.

The board service does not import this module. It is intentionally kept as an
offline tool so model training and preference tuning only run when called by a
developer.
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = pathlib.Path(__file__).resolve().parents[1]
BOARD_DIR = ROOT / "board"
if str(BOARD_DIR) not in sys.path:
    sys.path.insert(0, str(BOARD_DIR))

from app.core import RecommendationEngine, color_family, normalize_category, split_tags  # noqa: E402


SYSTEM_PROMPT = (
    "你是智能衣柜穿搭推荐大模型。你必须基于用户衣柜、天气、场景和偏好给出可解释搭配，"
    "不要编造衣柜里不存在的单品。输出 JSON，字段包括 outfit、reason、missing_categories、confidence。"
)

DEFAULT_WEATHER_SCENARIOS = [
    {"city": "Hangzhou", "temperature_c": 4.0, "weather_text": "寒冷"},
    {"city": "Hangzhou", "temperature_c": 12.0, "weather_text": "微凉"},
    {"city": "Hangzhou", "temperature_c": 18.0, "weather_text": "多云"},
    {"city": "Hangzhou", "temperature_c": 26.0, "weather_text": "舒适"},
    {"city": "Hangzhou", "temperature_c": 31.0, "weather_text": "炎热"},
]

DEFAULT_OCCASIONS = ["school", "commute", "casual", "sport", "formal"]

POLYVORE_CATEGORY_MAP = {
    "tops": "top",
    "bottoms": "bottom",
    "shoes": "shoes",
    "outerwear": "outer",
    "bags": "accessory",
    "accessories": "accessory",
    "all-body": "dress",
}


@dataclass
class TrainingBundle:
    mode: str
    output_dir: pathlib.Path
    files: Dict[str, str]
    examples: int
    manifest_path: pathlib.Path


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: pathlib.Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def load_wardrobe_items(
    wardrobe_path: Optional[pathlib.Path] = None,
    db_path: Optional[pathlib.Path] = None,
) -> List[Dict[str, Any]]:
    if db_path:
        from app.core import WardrobeDB  # Imported lazily to avoid opening SQLite unless needed.

        return WardrobeDB(db_path).list_clothes()

    path = wardrobe_path or pathlib.Path(__file__).resolve().parent / "demo_wardrobe.json"
    data = read_json(path)
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("wardrobe data must be a list or an object with an items list")
    return [normalize_item(item) for item in items if isinstance(item, dict)]


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)
    normalized["id"] = str(normalized.get("id") or normalized.get("local_id") or normalized.get("name") or "")
    normalized["name"] = str(normalized.get("name") or "未命名单品")
    normalized["category"] = normalize_category(normalized.get("category"))
    normalized["color_family"] = color_family(normalized.get("color") or normalized.get("color_label"))
    normalized["season"] = ",".join(split_tags(normalized.get("season"))) or "all"
    normalized["occasion"] = ",".join(split_tags(normalized.get("occasion"))) or "all"
    normalized["warmth"] = _int_between(normalized.get("warmth"), 3, 1, 5)
    normalized["formality"] = _int_between(normalized.get("formality"), 2, 1, 5)
    normalized["favorite_score"] = _int_between(normalized.get("favorite_score"), 3, 1, 5)
    return normalized


def _int_between(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def compact_item(item: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "id",
        "name",
        "category",
        "color",
        "color_family",
        "material",
        "season",
        "occasion",
        "style",
        "warmth",
        "formality",
        "favorite_score",
    ]
    return {key: item.get(key) for key in keys if item.get(key) not in (None, "")}


def build_user_prompt(items: Sequence[Dict[str, Any]], weather: Dict[str, Any], occasion: str) -> str:
    payload = {
        "task": "recommend_outfit",
        "weather": weather,
        "occasion": occasion,
        "wardrobe": [compact_item(item) for item in items],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def recommendation_to_answer(result: Dict[str, Any]) -> Dict[str, Any]:
    recommendations = result.get("recommendations") or []
    first = recommendations[0] if recommendations else {}
    outfit = []
    for item in first.get("items") or []:
        outfit.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "category": item.get("category"),
                "color": item.get("color"),
            }
        )
    return {
        "outfit": outfit,
        "reason": first.get("reason") or result.get("explain") or [],
        "summary": first.get("summary") or "",
        "score": first.get("score", 0),
        "missing_categories": result.get("missing_categories") or [],
        "confidence": 0.86 if outfit else 0.25,
    }


def make_chat_example(prompt: str, answer: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
        ]
    }


def make_polyvore_completion_prompt(
    known_items: Sequence[Dict[str, Any]],
    candidate_items: Sequence[Dict[str, Any]],
) -> str:
    payload = {
        "task": "complete_outfit",
        "known_outfit": [compact_item(item) for item in known_items],
        "candidate_items": [compact_item(item) for item in candidate_items],
        "instruction": "从 candidate_items 中选择最适合补全 known_outfit 的单品，只能选择候选列表中存在的单品。",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def make_polyvore_completion_answer(
    known_items: Sequence[Dict[str, Any]],
    selected_item: Dict[str, Any],
    confidence: float = 0.82,
) -> Dict[str, Any]:
    outfit = [compact_item(item) for item in known_items] + [compact_item(selected_item)]
    known_categories = [str(item.get("category") or "") for item in known_items if item.get("category")]
    selected_category = str(selected_item.get("category") or "")
    reasons = [
        "该单品来自真实 Polyvore 搭配组合，和当前已选单品存在搭配兼容关系。",
        "候选单品的类别为 %s，可补全当前搭配中的空缺位置。" % (selected_category or "unknown"),
    ]
    if known_categories:
        reasons.append("当前搭配已包含 %s，选择该单品后形成更完整的 outfit。" % "、".join(known_categories[:5]))
    return {
        "selected_item": compact_item(selected_item),
        "outfit": outfit,
        "reason": reasons,
        "missing_categories": [],
        "confidence": confidence,
    }


def normalize_polyvore_item(item_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    semantic = str(metadata.get("semantic_category") or "").strip()
    name = (
        str(metadata.get("title") or "").strip()
        or str(metadata.get("url_name") or "").strip()
        or "polyvore item %s" % item_id
    )
    category = POLYVORE_CATEGORY_MAP.get(semantic, semantic or "unknown")
    return {
        "id": str(item_id),
        "name": name[:120],
        "category": category,
        "polyvore_category": str(metadata.get("catgeories") or metadata.get("categories") or ""),
        "semantic_category": semantic,
        "description": str(metadata.get("description") or "")[:240],
    }


def load_polyvore_metadata(path: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError("polyvore metadata must be a JSON object")
    return {str(key): value for key, value in data.items() if isinstance(value, dict)}


def build_polyvore_item_index(
    outfit_rows: Sequence[Dict[str, Any]],
    metadata: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    for outfit in outfit_rows:
        set_id = str(outfit.get("set_id") or "")
        for entry in outfit.get("items") or []:
            if not isinstance(entry, dict):
                continue
            item_id = str(entry.get("item_id") or "")
            index = str(entry.get("index") or "")
            if not set_id or not item_id or not index:
                continue
            meta = metadata.get(item_id, {})
            indexed["%s_%s" % (set_id, index)] = normalize_polyvore_item(item_id, meta)
    return indexed


def build_polyvore_sft_examples(
    fill_in_blank_rows: Sequence[Dict[str, Any]],
    item_index: Dict[str, Dict[str, Any]],
    max_examples: int = 0,
) -> List[Dict[str, Any]]:
    examples = []
    for row in fill_in_blank_rows:
        known = [item_index[token] for token in row.get("question") or [] if token in item_index]
        candidates = [item_index[token] for token in row.get("answers") or [] if token in item_index]
        if not known or len(candidates) < 2:
            continue
        selected = candidates[0]
        prompt = make_polyvore_completion_prompt(known, candidates)
        answer = make_polyvore_completion_answer(known, selected)
        examples.append(make_chat_example(prompt, answer))
        if max_examples and len(examples) >= max_examples:
            break
    return examples


def build_polyvore_preference_pairs(
    fill_in_blank_rows: Sequence[Dict[str, Any]],
    item_index: Dict[str, Dict[str, Any]],
    max_pairs: int = 0,
) -> List[Dict[str, Any]]:
    pairs = []
    for row in fill_in_blank_rows:
        known = [item_index[token] for token in row.get("question") or [] if token in item_index]
        candidates = [item_index[token] for token in row.get("answers") or [] if token in item_index]
        if not known or len(candidates) < 2:
            continue
        prompt = make_polyvore_completion_prompt(known, candidates)
        chosen_answer = make_polyvore_completion_answer(known, candidates[0], confidence=0.84)
        for rejected_item in candidates[1:]:
            rejected_answer = make_polyvore_completion_answer(known, rejected_item, confidence=0.38)
            rejected_answer["reason"] = [
                "该候选是 fill-in-the-blank 负样本，相比正确答案与当前搭配的兼容性更弱。"
            ]
            pairs.append(
                {
                    "prompt": prompt,
                    "chosen": json.dumps(chosen_answer, ensure_ascii=False),
                    "rejected": json.dumps(rejected_answer, ensure_ascii=False),
                    "metadata": {
                        "source": "polyvore_fill_in_blank",
                        "blank_position": row.get("blank_position"),
                        "chosen_item_id": candidates[0].get("id"),
                        "rejected_item_id": rejected_item.get("id"),
                    },
                }
            )
            if max_pairs and len(pairs) >= max_pairs:
                return pairs
    return pairs


def build_sft_examples(
    items: Sequence[Dict[str, Any]],
    weather_scenarios: Sequence[Dict[str, Any]] = DEFAULT_WEATHER_SCENARIOS,
    occasions: Sequence[str] = DEFAULT_OCCASIONS,
    max_examples: int = 0,
) -> List[Dict[str, Any]]:
    engine = RecommendationEngine()
    normalized_items = [normalize_item(item) for item in items]
    examples = []
    for weather in weather_scenarios:
        for occasion in occasions:
            result = engine.recommend(normalized_items, weather, occasion=occasion, limit=1)
            prompt = build_user_prompt(normalized_items, weather, occasion)
            answer = recommendation_to_answer(result)
            examples.append(make_chat_example(prompt, answer))
            if max_examples and len(examples) >= max_examples:
                return examples
    return examples


def load_feedback_events(path: Optional[pathlib.Path]) -> List[Dict[str, Any]]:
    if not path:
        return []
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    data = path.read_text(encoding="utf-8").strip()
    if not data:
        return []
    if data.startswith("["):
        payload = json.loads(data)
        return payload if isinstance(payload, list) else []
    events = []
    for line in data.splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def build_preference_pairs(
    items: Sequence[Dict[str, Any]],
    feedback_events: Sequence[Dict[str, Any]] = (),
    weather: Optional[Dict[str, Any]] = None,
    occasion: str = "casual",
) -> List[Dict[str, Any]]:
    normalized_items = [normalize_item(item) for item in items]
    by_id = {str(item.get("id") or item.get("name")): item for item in normalized_items}
    positives, negatives = _split_items_by_preference(normalized_items, feedback_events, by_id)
    pairs = []
    scenario = weather or {"city": "Hangzhou", "temperature_c": 24.0, "weather_text": "舒适"}
    prompt = build_user_prompt(normalized_items, scenario, occasion)
    for chosen, rejected in _pair_by_category(positives, negatives):
        chosen_answer = {
            "outfit": [compact_item(chosen)],
            "reason": [
                "%s 的用户喜爱分更高，后续推荐应优先考虑" % chosen.get("name"),
                "同类单品中 %s 的历史偏好信号弱于该选择" % rejected.get("name"),
            ],
            "missing_categories": [],
            "confidence": 0.78,
        }
        rejected_answer = {
            "outfit": [compact_item(rejected)],
            "reason": ["该单品不符合当前用户的显式喜好信号"],
            "missing_categories": [],
            "confidence": 0.42,
        }
        pairs.append(
            {
                "prompt": prompt,
                "chosen": json.dumps(chosen_answer, ensure_ascii=False),
                "rejected": json.dumps(rejected_answer, ensure_ascii=False),
                "metadata": {
                    "chosen_item_id": chosen.get("id"),
                    "rejected_item_id": rejected.get("id"),
                    "category": chosen.get("category"),
                    "source": "feedback" if feedback_events else "favorite_score",
                },
            }
        )
    return pairs


def preference_pairs_to_sft(pairs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    examples = []
    for pair in pairs:
        try:
            answer = json.loads(pair["chosen"])
        except (KeyError, json.JSONDecodeError):
            continue
        examples.append(make_chat_example(str(pair.get("prompt") or ""), answer))
    return examples


def _split_items_by_preference(
    items: Sequence[Dict[str, Any]],
    feedback_events: Sequence[Dict[str, Any]],
    by_id: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    positive_ids = set()
    negative_ids = set()
    for event in feedback_events:
        item_id = str(event.get("item_id") or event.get("id") or event.get("clothing_id") or "")
        action = str(event.get("action") or event.get("feedback") or event.get("label") or "").lower()
        rating = _int_between(event.get("rating") or event.get("score"), 0, -5, 5)
        liked = action in {"like", "liked", "favorite", "wear", "accept", "chosen", "positive"} or rating >= 4
        disliked = action in {"dislike", "skip", "reject", "negative"} or rating <= 2 and rating != 0
        if item_id and liked:
            positive_ids.add(item_id)
        if item_id and disliked:
            negative_ids.add(item_id)

    positives = [by_id[item_id] for item_id in positive_ids if item_id in by_id]
    negatives = [by_id[item_id] for item_id in negative_ids if item_id in by_id]
    if not positives:
        positives = [item for item in items if _int_between(item.get("favorite_score"), 3, 1, 5) >= 4]
    if not negatives:
        negatives = [item for item in items if _int_between(item.get("favorite_score"), 3, 1, 5) <= 3]
    positives.sort(key=lambda item: (_int_between(item.get("favorite_score"), 3, 1, 5), str(item.get("name"))), reverse=True)
    negatives.sort(key=lambda item: (_int_between(item.get("favorite_score"), 3, 1, 5), str(item.get("name"))))
    return positives, negatives


def _pair_by_category(
    positives: Sequence[Dict[str, Any]],
    negatives: Sequence[Dict[str, Any]],
) -> Iterable[Tuple[Dict[str, Any], Dict[str, Any]]]:
    used = set()
    for positive in positives:
        category = positive.get("category")
        candidate = None
        for negative in negatives:
            key = negative.get("id") or negative.get("name")
            if key in used:
                continue
            if negative.get("category") == category:
                candidate = negative
                break
        if candidate is None:
            for negative in negatives:
                key = negative.get("id") or negative.get("name")
                if key not in used:
                    candidate = negative
                    break
        if candidate is None or candidate is positive:
            continue
        used.add(candidate.get("id") or candidate.get("name"))
        yield positive, candidate


def write_bundle_manifest(
    output_dir: pathlib.Path,
    mode: str,
    files: Dict[str, str],
    base_model: str,
    examples: int,
    notes: Sequence[str],
) -> pathlib.Path:
    manifest = {
        "mode": mode,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "base_model": base_model,
        "examples": examples,
        "files": files,
        "training": {
            "enabled_by_default": False,
            "recommended_method": "LoRA or provider fine-tuning with chat JSONL",
            "default_hyperparameters": {
                "epochs": 3,
                "learning_rate": "2e-5",
                "lora_rank": 16,
                "batch_size": 2,
            },
        },
        "notes": list(notes),
    }
    path = output_dir / "training_manifest.json"
    write_json(path, manifest)
    return path


def build_base_sft_bundle(
    items: Sequence[Dict[str, Any]],
    output_dir: pathlib.Path,
    base_model: str,
    max_examples: int = 0,
) -> TrainingBundle:
    output_dir.mkdir(parents=True, exist_ok=True)
    examples = build_sft_examples(items, max_examples=max_examples)
    train_path = output_dir / "outfit_sft_train.jsonl"
    count = write_jsonl(train_path, examples)
    write_json(output_dir / "wardrobe_snapshot.json", [compact_item(normalize_item(item)) for item in items])
    files = {
        "sft_train": str(train_path),
        "wardrobe_snapshot": str(output_dir / "wardrobe_snapshot.json"),
    }
    manifest_path = write_bundle_manifest(
        output_dir,
        "base_sft",
        files,
        base_model,
        count,
        [
            "This bundle prepares outfit-recommendation instruction data.",
            "No training job is launched unless a developer explicitly runs a trainer with these files.",
        ],
    )
    return TrainingBundle("base_sft", output_dir, files, count, manifest_path)


def build_preference_tuning_bundle(
    items: Sequence[Dict[str, Any]],
    output_dir: pathlib.Path,
    base_model: str,
    feedback_events: Sequence[Dict[str, Any]] = (),
) -> TrainingBundle:
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs = build_preference_pairs(items, feedback_events)
    sft_examples = preference_pairs_to_sft(pairs)
    dpo_path = output_dir / "user_preference_dpo.jsonl"
    sft_path = output_dir / "user_preference_continue_sft.jsonl"
    dpo_count = write_jsonl(dpo_path, pairs)
    write_jsonl(sft_path, sft_examples)
    files = {
        "preference_dpo": str(dpo_path),
        "continue_sft": str(sft_path),
    }
    manifest_path = write_bundle_manifest(
        output_dir,
        "user_preference_continue",
        files,
        base_model,
        dpo_count,
        [
            "Preference pairs are derived from explicit feedback when provided, otherwise from favorite_score.",
            "Use DPO data for preference alignment or continue_sft for a simpler incremental SFT run.",
            "The production recommendation service is not wired to call this training path.",
        ],
    )
    return TrainingBundle("user_preference_continue", output_dir, files, dpo_count, manifest_path)


def validate_jsonl(path: pathlib.Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            json.loads(line)
            count += 1
    return count
