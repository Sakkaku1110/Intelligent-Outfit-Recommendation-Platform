from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .algorithm import WeatherContext


OPEN_METEO_ENDPOINT = "https://api.open-meteo.com/v1/forecast"


def load_weather_snapshot(path: Path) -> WeatherContext:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    return WeatherContext.from_mapping(data.get("weather", data))


def fetch_open_meteo_weather(
    latitude: float,
    longitude: float,
    city: str = "unknown",
    timeout: float = 8.0,
) -> WeatherContext:
    """Fetch current weather on SS928 Linux without third-party dependencies."""
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,weather_code",
        }
    )
    url = f"{OPEN_METEO_ENDPOINT}?{query}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))

    current = payload.get("current", {})
    return WeatherContext(
        temperature_c=float(current.get("temperature_2m", 22.0)),
        humidity=float(current.get("relative_humidity_2m", 50.0)),
        condition=weather_code_to_condition(current.get("weather_code")),
        city=city,
    )


def weather_code_to_condition(code: Any) -> str:
    try:
        value = int(code)
    except (TypeError, ValueError):
        return "clear"
    if value in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "rain"
    if value in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if value in {45, 48}:
        return "fog"
    if value in {95, 96, 99}:
        return "storm"
    if value in {1, 2, 3}:
        return "cloudy"
    return "clear"
