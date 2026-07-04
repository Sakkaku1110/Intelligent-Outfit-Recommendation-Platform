from __future__ import annotations

from dataclasses import dataclass

from ..algorithm import (
    UserRequest,
    WardrobeItem,
    WeatherContext,
    recommend_outfits,
)


@dataclass
class SS928RecommendationService:
    """Algorithm-first service intended to run on SS928 Linux."""

    items: list[WardrobeItem]

    def recommend(
        self,
        weather: WeatherContext,
        request: UserRequest,
        top_k: int = 5,
    ):
        return recommend_outfits(self.items, weather, request, top_k=top_k)
