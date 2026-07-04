"""Core package for outfit recommendation."""

from .algorithm import (
    UserRequest,
    WardrobeItem,
    WeatherContext,
    recommend_outfits,
)

__all__ = [
    "OutfitCompatibilityModel",
    "UserRequest",
    "WardrobeItem",
    "WeatherContext",
    "recommend_outfits",
]


def __getattr__(name: str):
    if name == "OutfitCompatibilityModel":
        from .model import OutfitCompatibilityModel

        return OutfitCompatibilityModel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
