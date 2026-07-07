#!/usr/bin/env python3
"""Rule-based material hints from GY-AS7341 spectral readings.

The classifier is intentionally small and deterministic so it can run on the
SS928 board without machine-learning dependencies. It is a first-pass material
hint: good enough for competition demos, and explicit about low-light captures
where the sensor data is not reliable.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


SPECTRAL_CHANNELS = ("f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8")
REQUIRED_CHANNELS = SPECTRAL_CHANNELS + ("clear", "nir")


@dataclass(frozen=True)
class SpectralReading:
    f1: float
    f2: float
    f3: float
    f4: float
    f5: float
    f6: float
    f7: float
    f8: float
    clear: float
    nir: float

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "SpectralReading":
        values: Dict[str, float] = {}
        missing: List[str] = []
        for name in REQUIRED_CHANNELS:
            value = _payload_value(payload, name)
            if value is None:
                missing.append(name)
                continue
            try:
                values[name] = max(0.0, float(value))
            except (TypeError, ValueError):
                raise ValueError("channel %s is not numeric" % name)
        if missing:
            raise ValueError("missing AS7341 channels: %s" % ", ".join(missing))
        return cls(**values)

    def visible(self) -> List[float]:
        return [getattr(self, name) for name in SPECTRAL_CHANNELS]

    def to_dict(self) -> Dict[str, float]:
        return {name: getattr(self, name) for name in REQUIRED_CHANNELS}


@dataclass(frozen=True)
class MaterialProfile:
    material: str
    label: str
    features: Dict[str, float]
    weights: Dict[str, float]


def has_as7341_channels(payload: Dict[str, Any]) -> bool:
    return all(_payload_value(payload, name) is not None for name in REQUIRED_CHANNELS)


def classify_material(payload: Dict[str, Any], top_k: int = 3) -> Dict[str, Any]:
    reading = SpectralReading.from_payload(payload)
    features = extract_spectral_features(reading)
    quality = assess_capture_quality(reading, features)

    if quality["quality"] != "ok":
        candidate = {
            "material": quality["material"],
            "label": quality["label"],
            "confidence": 0.12,
            "score": 0.0,
            "reason": quality["reason"],
        }
        return {
            "sensor": "GY-AS7341",
            "material": candidate["material"],
            "label": candidate["label"],
            "confidence": candidate["confidence"],
            "quality": quality["quality"],
            "reason": quality["reason"],
            "features": features,
            "candidates": [candidate],
        }

    candidates = _rank_profiles(features)
    top_k = max(1, int(top_k or 1))
    selected = candidates[:top_k]
    best = selected[0]
    return {
        "sensor": "GY-AS7341",
        "material": best["material"],
        "label": best["label"],
        "confidence": best["confidence"],
        "quality": "ok",
        "reason": best["reason"],
        "features": features,
        "candidates": selected,
    }


def classify_json_lines(lines: Iterable[str], top_k: int = 3) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for line in lines:
        text = line.strip()
        if not text or not text.startswith("{"):
            continue
        payload = json.loads(text)
        if not isinstance(payload, dict):
            continue
        if has_as7341_channels(payload):
            results.append(classify_material(payload, top_k=top_k))
    return results


def extract_spectral_features(reading: SpectralReading) -> Dict[str, float]:
    visible = reading.visible()
    total = sum(visible)
    mean = total / max(1, len(visible))
    low = max(1e-6, mean)
    blue = visible[0] + visible[1]
    mid = visible[2] + visible[3] + visible[4]
    red = visible[5] + visible[6] + visible[7]
    warm = visible[4] + visible[5] + visible[6] + visible[7]
    spread = max(visible) - min(visible)
    first_half = sum(visible[:4])
    second_half = sum(visible[4:])

    return {
        "visible_total": round(total, 4),
        "clear": round(reading.clear, 4),
        "nir": round(reading.nir, 4),
        "brightness": round(math.log1p(total) / 8.0, 4),
        "red_blue_ratio": round((red + 1.0) / (blue + 1.0), 4),
        "middle_ratio": round((mid + 1.0) / (total + 1.0), 4),
        "nir_ratio": round((reading.nir + 1.0) / (reading.clear + 1.0), 4),
        "clear_ratio": round((reading.clear + 1.0) / (total + 1.0), 4),
        "spectral_slope": round((second_half - first_half) / (total + 1.0), 4),
        "flatness": round(max(0.0, 1.0 - spread / low), 4),
        "warmth": round((warm + 1.0) / (total + 1.0), 4),
    }


def assess_capture_quality(
    reading: SpectralReading, features: Optional[Dict[str, float]] = None
) -> Dict[str, str]:
    features = features or extract_spectral_features(reading)
    visible_total = float(features["visible_total"])
    clear = float(features["clear"])
    if visible_total < 80 or clear < 40:
        return {
            "quality": "low_light",
            "material": "unknown_low_light",
            "label": "unknown_low_light",
            "reason": "AS7341 signal is too weak; use fixed white light and scan close to the fabric.",
        }
    if visible_total > 60000 or clear > 60000:
        return {
            "quality": "saturated",
            "material": "unknown_saturated",
            "label": "unknown_saturated",
            "reason": "AS7341 signal is saturated; reduce LED strength or increase distance.",
        }
    return {
        "quality": "ok",
        "material": "",
        "label": "",
        "reason": "capture quality is usable.",
    }


def _rank_profiles(features: Dict[str, float]) -> List[Dict[str, Any]]:
    raw_scores: List[Tuple[MaterialProfile, float]] = []
    for profile in _profiles():
        distance = 0.0
        weight_sum = 0.0
        for key, expected in profile.features.items():
            observed = float(features.get(key, 0.0))
            weight = float(profile.weights.get(key, 1.0))
            distance += abs(observed - expected) * weight
            weight_sum += weight
        normalized = distance / max(1e-6, weight_sum)
        score = max(0.0, 1.0 - normalized)
        raw_scores.append((profile, score))

    raw_scores.sort(key=lambda item: item[1], reverse=True)
    best_score = raw_scores[0][1]
    second_score = raw_scores[1][1] if len(raw_scores) > 1 else 0.0
    margin = max(0.0, best_score - second_score)

    candidates: List[Dict[str, Any]] = []
    for profile, score in raw_scores:
        confidence = 0.25 + score * 0.5
        if profile is raw_scores[0][0]:
            confidence += min(0.16, margin * 0.8)
        confidence = max(0.18, min(0.92, confidence))
        candidates.append(
            {
                "material": profile.material,
                "label": profile.label,
                "confidence": round(confidence, 3),
                "score": round(score, 3),
                "reason": _reason_for(profile.material, features),
            }
        )
    return candidates


def _profiles() -> List[MaterialProfile]:
    shared_weights = {
        "red_blue_ratio": 0.9,
        "middle_ratio": 0.55,
        "nir_ratio": 0.85,
        "spectral_slope": 1.0,
        "flatness": 0.7,
        "warmth": 0.75,
        "clear_ratio": 0.35,
    }
    return [
        MaterialProfile(
            "cotton",
            "cotton",
            {
                "red_blue_ratio": 1.35,
                "middle_ratio": 0.38,
                "nir_ratio": 0.20,
                "spectral_slope": 0.04,
                "flatness": 0.58,
                "warmth": 0.53,
                "clear_ratio": 1.05,
            },
            shared_weights,
        ),
        MaterialProfile(
            "linen",
            "linen",
            {
                "red_blue_ratio": 1.55,
                "middle_ratio": 0.37,
                "nir_ratio": 0.24,
                "spectral_slope": 0.08,
                "flatness": 0.48,
                "warmth": 0.57,
                "clear_ratio": 1.0,
            },
            shared_weights,
        ),
        MaterialProfile(
            "wool",
            "wool",
            {
                "red_blue_ratio": 1.85,
                "middle_ratio": 0.35,
                "nir_ratio": 0.32,
                "spectral_slope": 0.12,
                "flatness": 0.38,
                "warmth": 0.62,
                "clear_ratio": 0.92,
            },
            shared_weights,
        ),
        MaterialProfile(
            "denim",
            "denim",
            {
                "red_blue_ratio": 0.58,
                "middle_ratio": 0.45,
                "nir_ratio": 0.21,
                "spectral_slope": -0.18,
                "flatness": 0.26,
                "warmth": 0.32,
                "clear_ratio": 1.12,
            },
            shared_weights,
        ),
        MaterialProfile(
            "leather",
            "leather",
            {
                "red_blue_ratio": 4.2,
                "middle_ratio": 0.26,
                "nir_ratio": 0.43,
                "spectral_slope": 0.38,
                "flatness": 0.0,
                "warmth": 0.76,
                "clear_ratio": 1.08,
            },
            shared_weights,
        ),
        MaterialProfile(
            "silk_satin",
            "silk_or_satin",
            {
                "red_blue_ratio": 1.2,
                "middle_ratio": 0.39,
                "nir_ratio": 0.16,
                "spectral_slope": 0.03,
                "flatness": 0.72,
                "warmth": 0.51,
                "clear_ratio": 1.32,
            },
            shared_weights,
        ),
        MaterialProfile(
            "polyester",
            "polyester",
            {
                "red_blue_ratio": 1.05,
                "middle_ratio": 0.40,
                "nir_ratio": 0.13,
                "spectral_slope": 0.0,
                "flatness": 0.82,
                "warmth": 0.50,
                "clear_ratio": 1.24,
            },
            shared_weights,
        ),
    ]


def _reason_for(material: str, features: Dict[str, float]) -> str:
    ratio = features.get("red_blue_ratio", 0)
    nir_ratio = features.get("nir_ratio", 0)
    slope = features.get("spectral_slope", 0)
    flatness = features.get("flatness", 0)
    return (
        "%s matched by red_blue_ratio=%.2f, nir_ratio=%.2f, slope=%.2f, flatness=%.2f"
        % (material, ratio, nir_ratio, slope, flatness)
    )


def _payload_value(payload: Dict[str, Any], name: str) -> Any:
    aliases = (name, name.upper(), name.capitalize())
    for key in aliases:
        if key in payload:
            return payload[key]
    channels = payload.get("channels")
    if isinstance(channels, dict):
        for key in aliases:
            if key in channels:
                return channels[key]
    spectral = payload.get("spectral")
    if isinstance(spectral, dict):
        for key in aliases:
            if key in spectral:
                return spectral[key]
    return None
