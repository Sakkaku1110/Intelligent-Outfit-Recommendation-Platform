from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GYAS7341Reading:
    channels: dict[str, float]
    clear: float | None = None
    nir: float | None = None


def estimate_fabric_profile(reading: GYAS7341Reading) -> dict[str, object]:
    """Convert a spectral reading into prototype-level fabric features."""
    total = sum(max(value, 0.0) for value in reading.channels.values())
    if total <= 0:
        return {"material_hint": "unknown", "thickness": 3, "confidence": 0.0}

    red = reading.channels.get("f8", reading.channels.get("red", 0.0))
    green = reading.channels.get("f5", reading.channels.get("green", 0.0))
    blue = reading.channels.get("f2", reading.channels.get("blue", 0.0))
    nir = reading.nir or reading.channels.get("nir", 0.0)
    visible_balance = (red + green + blue) / total
    nir_ratio = nir / max(total + nir, 1.0)

    if nir_ratio > 0.35:
        material_hint = "wool"
        thickness = 4
    elif visible_balance > 0.55:
        material_hint = "cotton"
        thickness = 2
    else:
        material_hint = "polyester"
        thickness = 3

    return {
        "material_hint": material_hint,
        "thickness": thickness,
        "confidence": round(min(0.95, 0.45 + abs(nir_ratio - 0.25)), 2),
    }
