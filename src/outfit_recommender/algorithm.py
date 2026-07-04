from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


THICKNESS_LABELS = {
    "very_light": 1,
    "thin": 1,
    "light": 2,
    "medium": 3,
    "warm": 4,
    "thick": 4,
    "heavy": 5,
}

OCCASION_STYLE_MATCHES = {
    "formal": {"formal", "business", "commute"},
    "business": {"formal", "business", "commute"},
    "commute": {"commute", "business", "casual"},
    "casual": {"casual", "commute", "sport"},
    "sport": {"sport", "casual"},
    "outdoor": {"outdoor", "sport", "casual"},
    "date": {"date", "casual", "formal"},
}

BREATHABLE_MATERIALS = {"cotton", "linen", "silk", "viscose"}
WARM_MATERIALS = {"wool", "cashmere", "fleece", "down", "knit"}
RAIN_READY_MATERIALS = {"polyester", "nylon", "waterproof"}


@dataclass(frozen=True)
class WeatherContext:
    temperature_c: float
    humidity: float = 50.0
    condition: str = "clear"
    city: str = "unknown"

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "WeatherContext":
        return cls(
            temperature_c=float(
                data.get("temperature_c", data.get("temperature", 22.0))
            ),
            humidity=float(data.get("humidity", 50.0)),
            condition=str(data.get("condition", "clear")).lower(),
            city=str(data.get("city", "unknown")),
        )


@dataclass(frozen=True)
class UserRequest:
    occasion: str = "casual"
    prefer_warmth: int | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "UserRequest":
        prefer_warmth = data.get("prefer_warmth")
        return cls(
            occasion=str(data.get("occasion", "casual")).lower(),
            prefer_warmth=int(prefer_warmth) if prefer_warmth is not None else None,
        )


@dataclass(frozen=True)
class WardrobeItem:
    id: str
    name: str
    category: str
    styles: tuple[str, ...]
    thickness: int
    material: str = "unknown"
    color: str = "unknown"
    in_stock: bool = True
    days_since_wash: int = 0
    days_in_stock: int = 0

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "WardrobeItem":
        styles = data.get("styles", data.get("style", "casual"))
        if isinstance(styles, str):
            styles = (styles,)
        thickness = data.get("thickness", data.get("warmth", 3))
        if isinstance(thickness, str):
            thickness_value = THICKNESS_LABELS.get(thickness.lower(), 3)
        else:
            thickness_value = int(thickness)
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            category=str(data["category"]),
            styles=tuple(str(style).lower() for style in styles),
            thickness=max(1, min(5, thickness_value)),
            material=str(data.get("material", "unknown")).lower(),
            color=str(data.get("color", "unknown")).lower(),
            in_stock=bool(data.get("in_stock", True)),
            days_since_wash=int(data.get("days_since_wash", 0)),
            days_in_stock=int(data.get("days_in_stock", 0)),
        )


@dataclass(frozen=True)
class ScoredItem:
    item: WardrobeItem
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class OutfitRecommendation:
    items: tuple[WardrobeItem, ...]
    score: float
    reasons: tuple[str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "category": item.category,
                    "style": list(item.styles),
                    "thickness": item.thickness,
                    "material": item.material,
                    "in_stock": item.in_stock,
                }
                for item in self.items
            ],
            "reasons": list(self.reasons),
        }


def load_wardrobe(path: Path) -> list[WardrobeItem]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    raw_items = data["items"] if isinstance(data, dict) else data
    return [WardrobeItem.from_mapping(item) for item in raw_items]


def load_recommendation_context(path: Path | None) -> tuple[WeatherContext, UserRequest]:
    if path is None:
        return WeatherContext(temperature_c=22.0), UserRequest()
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    return (
        WeatherContext.from_mapping(data.get("weather", data)),
        UserRequest.from_mapping(data.get("user_request", data)),
    )


def target_thickness(weather: WeatherContext, request: UserRequest) -> int:
    if request.prefer_warmth is not None:
        return max(1, min(5, request.prefer_warmth))
    temperature = weather.temperature_c
    if temperature <= 5:
        return 5
    if temperature <= 12:
        return 4
    if temperature <= 20:
        return 3
    if temperature <= 27:
        return 2
    return 1


def score_item(
    item: WardrobeItem,
    weather: WeatherContext,
    request: UserRequest,
) -> ScoredItem:
    if not item.in_stock:
        return ScoredItem(item, -100.0, ("not in stock",))

    score = 35.0
    reasons: list[str] = ["in stock"]

    expected_thickness = target_thickness(weather, request)
    thickness_gap = abs(item.thickness - expected_thickness)
    score += max(0.0, 20.0 - thickness_gap * 7.0)
    if thickness_gap == 0:
        reasons.append("thickness matches current temperature")
    elif thickness_gap == 1:
        reasons.append("thickness is acceptable for current temperature")
    else:
        reasons.append("thickness has a temperature mismatch")

    matched_styles = OCCASION_STYLE_MATCHES.get(request.occasion, {request.occasion})
    if set(item.styles) & matched_styles:
        score += 20.0
        reasons.append(f"style matches {request.occasion}")
    elif "basic" in item.styles:
        score += 8.0
        reasons.append("basic style can be reused")
    else:
        score -= 12.0
        reasons.append(f"style is less suitable for {request.occasion}")

    condition = weather.condition
    if "rain" in condition:
        if item.category == "outerwear" or item.material in RAIN_READY_MATERIALS:
            score += 12.0
            reasons.append("rain-ready item")
        elif item.category == "shoes":
            score -= 6.0
            reasons.append("check shoes for rainy weather")
    if weather.humidity >= 75:
        if item.material in BREATHABLE_MATERIALS:
            score += 8.0
            reasons.append("breathable for high humidity")
        elif item.material in WARM_MATERIALS and weather.temperature_c >= 20:
            score -= 10.0
            reasons.append("warm material may feel stuffy")

    if item.days_since_wash <= 1:
        score += 8.0
        reasons.append("recently washed")
    elif item.days_since_wash <= 4:
        score += 2.0
        reasons.append("clean status is acceptable")
    elif item.days_since_wash <= 7:
        score -= 10.0
        reasons.append("washing interval is getting long")
    else:
        score -= 25.0
        reasons.append("too many days without washing")

    if item.days_in_stock >= 20:
        score += 4.0
        reasons.append("long unused item can be rotated")

    return ScoredItem(item, max(0.0, min(100.0, score)), tuple(reasons))


def generate_candidates(items: list[WardrobeItem]) -> list[tuple[WardrobeItem, ...]]:
    by_category: dict[str, list[WardrobeItem]] = {}
    for item in items:
        if item.in_stock:
            by_category.setdefault(item.category, []).append(item)

    candidates: list[tuple[WardrobeItem, ...]] = []
    outerwear_options = [None, *by_category.get("outerwear", [])]
    for top, bottom, shoes, outerwear in itertools.product(
        by_category.get("tops", []),
        by_category.get("bottoms", []),
        by_category.get("shoes", []),
        outerwear_options,
    ):
        candidates.append(tuple(item for item in (top, bottom, shoes, outerwear) if item))

    for dress, shoes, outerwear in itertools.product(
        by_category.get("all-body", []),
        by_category.get("shoes", []),
        outerwear_options,
    ):
        candidates.append(tuple(item for item in (dress, shoes, outerwear) if item))
    return candidates


def score_outfit(
    candidate: tuple[WardrobeItem, ...],
    weather: WeatherContext,
    request: UserRequest,
) -> OutfitRecommendation:
    scored_items = [score_item(item, weather, request) for item in candidate]
    item_average = sum(item.score for item in scored_items) / len(scored_items)
    score = item_average
    reasons: list[str] = []

    categories = {item.item.category for item in scored_items}
    if {"tops", "bottoms", "shoes"} <= categories or {"all-body", "shoes"} <= categories:
        score += 8.0
        reasons.append("complete outfit structure")
    else:
        score -= 20.0
        reasons.append("missing core outfit category")

    if weather.temperature_c <= 12 and "outerwear" not in categories:
        score -= 12.0
        reasons.append("cold weather but no outerwear")
    if "rain" in weather.condition and "outerwear" not in categories:
        score -= 8.0
        reasons.append("rainy weather but no outerwear")

    if len({item.item.color for item in scored_items if item.item.color != "unknown"}) <= 3:
        score += 4.0
        reasons.append("colors stay simple")

    for scored in sorted(scored_items, key=lambda result: result.score, reverse=True):
        reasons.extend(f"{scored.item.name}: {reason}" for reason in scored.reasons[:2])

    return OutfitRecommendation(
        items=tuple(item.item for item in scored_items),
        score=max(0.0, min(100.0, score)),
        reasons=tuple(reasons[:8]),
    )


def recommend_outfits(
    items: list[WardrobeItem],
    weather: WeatherContext,
    request: UserRequest,
    top_k: int = 5,
) -> list[OutfitRecommendation]:
    candidates = generate_candidates(items)
    ranked = sorted(
        (score_outfit(candidate, weather, request) for candidate in candidates),
        key=lambda recommendation: recommendation.score,
        reverse=True,
    )
    return ranked[:top_k]
