from outfit_recommender.hardware.gy_as7341 import (
    GYAS7341Reading,
    estimate_fabric_profile,
)
from outfit_recommender.hardware.imx179 import create_scan_event
from outfit_recommender.hardware.ws63 import parse_ws63_packet


def test_parse_ws63_packet() -> None:
    packet = parse_ws63_packet(
        '{"source":"ws63","event":"wardrobe_in","payload":{"item_id":"top_001"}}'
    )

    assert packet.source == "ws63"
    assert packet.event == "wardrobe_in"
    assert packet.payload["item_id"] == "top_001"


def test_estimate_fabric_profile_returns_demo_features() -> None:
    profile = estimate_fabric_profile(
        GYAS7341Reading(
            channels={"f1": 100, "f2": 120, "f5": 140, "f8": 130},
            nir=300,
        )
    )

    assert profile["material_hint"] in {"wool", "cotton", "polyester"}
    assert 1 <= profile["thickness"] <= 5


def test_create_scan_event_validates_direction() -> None:
    event = create_scan_event("in", image_path="/tmp/item.jpg", event_id="scan-1")

    assert event.event_id == "scan-1"
    assert event.direction == "in"
