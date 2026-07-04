import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outfit_recommender.algorithm import (  # noqa: E402
    UserRequest,
    WeatherContext,
    load_recommendation_context,
    load_wardrobe,
    recommend_outfits,
)
from outfit_recommender.weather import fetch_open_meteo_weather  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score outfit recommendations with the controllable rule-based "
            "algorithm used for the first-round demo."
        )
    )
    parser.add_argument("manifest", type=Path, help="Wardrobe manifest JSON.")
    parser.add_argument(
        "--context",
        type=Path,
        help="Fallback JSON file containing weather and user_request fields.",
    )
    parser.add_argument(
        "--weather-source",
        choices=("live", "context", "manual"),
        default="live",
        help=(
            "live fetches real weather by coordinates, context reads --context, "
            "and manual uses command-line weather values."
        ),
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--occasion", default="casual")
    parser.add_argument("--temperature-c", type=float, default=22.0)
    parser.add_argument("--humidity", type=float, default=50.0)
    parser.add_argument("--condition", default="clear")
    parser.add_argument("--city", default="Shanghai")
    parser.add_argument("--latitude", type=float, default=31.2304)
    parser.add_argument("--longitude", type=float, default=121.4737)
    parser.add_argument("--weather-timeout", type=float, default=8.0)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON for integration demos.",
    )
    return parser.parse_args()


def build_context(args: argparse.Namespace) -> tuple[WeatherContext, UserRequest]:
    if args.weather_source == "context":
        if not args.context:
            raise ValueError("--weather-source context requires --context")
        return load_recommendation_context(args.context)
    request = UserRequest(occasion=args.occasion.lower())
    if args.context:
        _, request = load_recommendation_context(args.context)
    if args.weather_source == "live":
        return (
            fetch_open_meteo_weather(
                latitude=args.latitude,
                longitude=args.longitude,
                city=args.city,
                timeout=args.weather_timeout,
            ),
            request,
        )
    return (
        WeatherContext(
            temperature_c=args.temperature_c,
            humidity=args.humidity,
            condition=args.condition.lower(),
            city=args.city,
        ),
        request,
    )


def main() -> None:
    args = parse_args()
    items = load_wardrobe(args.manifest)
    weather, request = build_context(args)
    recommendations = recommend_outfits(items, weather, request, top_k=args.top_k)

    if args.json:
        print(
            json.dumps(
                {
                    "mode": "algorithm",
                    "weather": weather.__dict__,
                    "user_request": request.__dict__,
                    "recommendations": [
                        recommendation.to_mapping()
                        for recommendation in recommendations
                    ],
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return

    print("Recommendation mode: algorithm scoring")
    print(f"Weather source: {args.weather_source}")
    print(
        "Weather: "
        f"{weather.city}, {weather.temperature_c:.1f}C, "
        f"humidity={weather.humidity:.0f}%, condition={weather.condition}"
    )
    print(f"Occasion: {request.occasion}")
    if not recommendations:
        print("No complete outfits could be generated from in-stock items.")
        return

    for rank, recommendation in enumerate(recommendations, start=1):
        names = ", ".join(item.name for item in recommendation.items)
        print(f"{rank}. score={recommendation.score:.2f} | {names}")
        for reason in recommendation.reasons[:4]:
            print(f"   - {reason}")


if __name__ == "__main__":
    main()
