#!/usr/bin/env python3
"""Rule-based material hints from GY-AS7341 spectral readings."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


SPECTRAL_CHANNELS = ("f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8")
REQUIRED_CHANNELS = SPECTRAL_CHANNELS + ("clear", "nir")
CHANNEL_ALIASES = {
    "f1": ("f1", "F1", "ch415", "415", "channel_415", "violet"),
    "f2": ("f2", "F2", "ch445", "445", "channel_445", "indigo"),
    "f3": ("f3", "F3", "ch480", "480", "channel_480", "blue"),
    "f4": ("f4", "F4", "ch515", "515", "channel_515", "cyan"),
    "f5": ("f5", "F5", "ch555", "555", "channel_555", "green"),
    "f6": ("f6", "F6", "ch590", "590", "channel_590", "yellow"),
    "f7": ("f7", "F7", "ch630", "630", "channel_630", "orange_red"),
    "f8": ("f8", "F8", "ch680", "680", "channel_680", "red"),
    "clear": ("clear", "CLEAR", "Clear", "c", "C"),
    "nir": ("nir", "NIR", "Nir", "near_ir", "nearInfrared"),
}


@dataclass(frozen=True)
class SpectralReading:
    values: Dict[str, float]

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "SpectralReading":
        return cls(_spectral_reading(payload))

    def visible(self) -> List[float]:
        return [self.values[name] for name in SPECTRAL_CHANNELS]

    def to_dict(self) -> Dict[str, float]:
        return dict(self.values)


@dataclass(frozen=True)
class MaterialProfile:
    material: str
    label: str
    features: Dict[str, float]
    weights: Dict[str, float]


def has_as7341_channels(payload: Dict[str, Any]) -> bool:
    try:
        _spectral_reading(payload)
        return True
    except ValueError:
        return False


def classify_material(payload: Dict[str, Any], top_k: int = 3) -> Dict[str, Any]:
    try:
        reading = SpectralReading.from_payload(payload)
    except ValueError as exc:
        return {
            "sensor": "GY-AS7341",
            "material": "unknown_invalid",
            "label": "无效光谱数据",
            "confidence": 0.0,
            "quality": "invalid",
            "reason": str(exc),
            "features": {},
            "candidates": [],
        }

    features = extract_spectral_features(reading)
    quality = assess_capture_quality(reading, features)

    if quality["quality"] != "ok":
        candidate = {
            "material": quality["material"],
            "label": quality["label"],
            "confidence": quality["confidence"],
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
    top_k = max(1, min(5, int(top_k or 3)))
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
        if not text or "{" not in text:
            continue
        try:
            payload = json.loads(text[text.find("{") :])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and has_as7341_channels(payload):
            results.append(classify_material(payload, top_k=top_k))
    return results


def extract_spectral_features(reading: SpectralReading) -> Dict[str, float]:
    values = reading.values
    visible = reading.visible()
    total = sum(visible)
    mean = total / max(1, len(visible))
    spread = max(visible) - min(visible)
    blue = visible[0] + visible[1] + visible[2]
    green = visible[3] + visible[4]
    red = visible[5] + visible[6] + visible[7]
    first_half = sum(visible[:4])
    second_half = sum(visible[4:])
    norm = [value / (total + 1.0) for value in visible]
    smoothness = 1.0 - min(1.0, sum(abs(norm[i + 1] - norm[i]) for i in range(7)) * 4.0)
    return {
        "visible_total": round(total, 4),
        "clear": round(values["clear"], 4),
        "nir": round(values["nir"], 4),
        "brightness": round(math.log1p(total) / 8.0, 4),
        "red_blue_ratio": round((red + 1.0) / (blue + 1.0), 4),
        "green_ratio": round((green + 1.0) / (total + 1.0), 4),
        "middle_ratio": round((green + visible[2] + 1.0) / (total + 1.0), 4),
        "nir_ratio": round((values["nir"] + 1.0) / (values["clear"] + 1.0), 4),
        "clear_ratio": round((values["clear"] + 1.0) / (total + 1.0), 4),
        "spectral_slope": round((second_half - first_half) / (total + 1.0), 4),
        "flatness": round(max(0.0, 1.0 - spread / max(1e-6, mean)), 4),
        "smoothness": round(max(0.0, smoothness), 4),
        "warmth": round((red + green + 1.0) / (total + 1.0), 4),
        "blue_fraction": round((blue + 1.0) / (total + 1.0), 4),
        "red_fraction": round((red + 1.0) / (total + 1.0), 4),
    }


def assess_capture_quality(
    reading: SpectralReading, features: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    features = features or extract_spectral_features(reading)
    visible_total = float(features["visible_total"])
    clear = float(features["clear"])
    visible = reading.visible()
    if visible_total < 80 or clear < 40:
        return {
            "quality": "low_light",
            "material": "unknown_low_light",
            "label": "光照过弱，无法可靠识别",
            "confidence": 0.12,
            "reason": "AS7341 signal is too weak; use fixed white light and scan close to the fabric.",
        }
    if visible_total > 60000 or clear > 60000 or max(visible) >= 65530:
        return {
            "quality": "saturated",
            "material": "unknown_saturated",
            "label": "光谱过曝，无法可靠识别",
            "confidence": 0.12,
            "reason": "AS7341 signal is saturated; reduce LED strength or increase distance.",
        }
    if min(visible) <= 0 and visible_total < 400:
        return {
            "quality": "unstable",
            "material": "unknown_unstable",
            "label": "光谱信号不稳定",
            "confidence": 0.1,
            "reason": "Some AS7341 channels are zero while total signal is weak.",
        }
    return {
        "quality": "ok",
        "material": "",
        "label": "",
        "confidence": 0.0,
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
    for index, (profile, score) in enumerate(raw_scores):
        confidence = 0.22 + score * 0.52
        if index == 0:
            confidence += min(0.18, margin * 0.9)
        candidates.append(
            {
                "material": profile.material,
                "label": profile.label,
                "confidence": round(max(0.18, min(0.94, confidence)), 3),
                "score": round(score, 3),
                "reason": _reason_for(profile.material, features),
            }
        )
    return candidates


def _profiles() -> List[MaterialProfile]:
    weights = {
        "red_blue_ratio": 0.85,
        "green_ratio": 0.45,
        "nir_ratio": 0.9,
        "clear_ratio": 0.35,
        "spectral_slope": 1.0,
        "flatness": 0.65,
        "smoothness": 0.45,
        "warmth": 0.7,
        "blue_fraction": 0.55,
        "red_fraction": 0.55,
    }
    return [
        MaterialProfile("cotton", "棉 / 棉混纺", {
            "red_blue_ratio": 1.15, "green_ratio": 0.25, "nir_ratio": 0.22,
            "clear_ratio": 1.05, "spectral_slope": 0.02, "flatness": 0.55,
            "smoothness": 0.62, "warmth": 0.63, "blue_fraction": 0.32, "red_fraction": 0.36,
        }, weights),
        MaterialProfile("linen", "亚麻 / 粗纹棉麻", {
            "red_blue_ratio": 1.38, "green_ratio": 0.24, "nir_ratio": 0.26,
            "clear_ratio": 0.98, "spectral_slope": 0.07, "flatness": 0.44,
            "smoothness": 0.48, "warmth": 0.66, "blue_fraction": 0.28, "red_fraction": 0.39,
        }, weights),
        MaterialProfile("wool", "羊毛 / 毛呢", {
            "red_blue_ratio": 1.75, "green_ratio": 0.22, "nir_ratio": 0.34,
            "clear_ratio": 0.92, "spectral_slope": 0.14, "flatness": 0.34,
            "smoothness": 0.42, "warmth": 0.70, "blue_fraction": 0.24, "red_fraction": 0.43,
        }, weights),
        MaterialProfile("denim", "牛仔 / 深色斜纹", {
            "red_blue_ratio": 0.58, "green_ratio": 0.28, "nir_ratio": 0.21,
            "clear_ratio": 1.12, "spectral_slope": -0.18, "flatness": 0.25,
            "smoothness": 0.34, "warmth": 0.52, "blue_fraction": 0.44, "red_fraction": 0.25,
        }, weights),
        MaterialProfile("leather", "皮革 / 亮面革", {
            "red_blue_ratio": 3.2, "green_ratio": 0.18, "nir_ratio": 0.43,
            "clear_ratio": 1.08, "spectral_slope": 0.34, "flatness": 0.08,
            "smoothness": 0.28, "warmth": 0.78, "blue_fraction": 0.16, "red_fraction": 0.52,
        }, weights),
        MaterialProfile("silk_satin", "丝绸 / 缎面", {
            "red_blue_ratio": 1.0, "green_ratio": 0.25, "nir_ratio": 0.16,
            "clear_ratio": 1.30, "spectral_slope": 0.0, "flatness": 0.72,
            "smoothness": 0.78, "warmth": 0.62, "blue_fraction": 0.34, "red_fraction": 0.34,
        }, weights),
        MaterialProfile("polyester", "涤纶 / 化纤", {
            "red_blue_ratio": 0.95, "green_ratio": 0.25, "nir_ratio": 0.14,
            "clear_ratio": 1.22, "spectral_slope": -0.02, "flatness": 0.82,
            "smoothness": 0.82, "warmth": 0.61, "blue_fraction": 0.35, "red_fraction": 0.33,
        }, weights),
    ]


def _reason_for(material: str, features: Dict[str, float]) -> str:
    return (
        "%s matched by red_blue_ratio=%.2f, nir_ratio=%.2f, slope=%.2f, flatness=%.2f"
        % (
            material,
            features.get("red_blue_ratio", 0),
            features.get("nir_ratio", 0),
            features.get("spectral_slope", 0),
            features.get("flatness", 0),
        )
    )


def _spectral_reading(payload: Dict[str, Any]) -> Dict[str, float]:
    samples = payload.get("samples")
    if isinstance(samples, list) and samples:
        readings = [_spectral_reading(item) for item in samples if isinstance(item, dict)]
        if not readings:
            raise ValueError("samples contains no AS7341 objects")
        return {
            name: sum(reading[name] for reading in readings) / len(readings)
            for name in REQUIRED_CHANNELS
        }

    values: Dict[str, float] = {}
    missing = []
    for name in REQUIRED_CHANNELS:
        value = _payload_value(payload, name)
        if value is None:
            missing.append(name)
            continue
        try:
            values[name] = max(0.0, float(value))
        except (TypeError, ValueError):
            raise ValueError("AS7341 channel %s is not numeric" % name)
    if missing:
        raise ValueError("missing AS7341 channels: %s" % ", ".join(missing))
    return values


def _payload_value(payload: Dict[str, Any], name: str) -> Any:
    containers = [payload]
    for key in ("channels", "spectral", "as7341", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            containers.append(value)
    for container in containers:
        for alias in CHANNEL_ALIASES[name]:
            if alias in container:
                return container[alias]
    return None
