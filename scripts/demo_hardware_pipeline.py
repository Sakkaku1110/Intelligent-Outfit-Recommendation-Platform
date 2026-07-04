import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outfit_recommender.hardware.gy_as7341 import (  # noqa: E402
    GYAS7341Reading,
    estimate_fabric_profile,
)
from outfit_recommender.hardware.ws63 import parse_ws63_packet  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo the WS63 to SS928 sensor packet flow."
    )
    parser.add_argument(
        "packet",
        type=Path,
        default=Path("examples/ws63_packet.example.json"),
        nargs="?",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw = args.packet.read_text(encoding="utf-8")
    packet = parse_ws63_packet(raw)
    payload = packet.payload

    result = {
        "source": packet.source,
        "event": packet.event,
        "item_id": payload.get("item_id"),
    }
    if packet.event == "spectral_reading":
        reading = GYAS7341Reading(
            channels=dict(payload.get("channels", {})),
            nir=payload.get("nir"),
        )
        result["fabric_profile"] = estimate_fabric_profile(reading)

    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
