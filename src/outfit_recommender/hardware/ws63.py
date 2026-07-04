from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WS63SensorPacket:
    source: str
    event: str
    payload: dict[str, Any]


def parse_ws63_packet(raw: str | bytes) -> WS63SensorPacket:
    """Parse a JSON packet sent by WS63 through UART, Wi-Fi, or BLE."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    return WS63SensorPacket(
        source=str(data.get("source", "ws63")),
        event=str(data["event"]),
        payload=dict(data.get("payload", {})),
    )


def build_inventory_update(packet: WS63SensorPacket) -> dict[str, Any]:
    if packet.event not in {"wardrobe_in", "wardrobe_out", "spectral_reading"}:
        raise ValueError(f"unsupported WS63 event: {packet.event}")
    return {
        "source": packet.source,
        "event": packet.event,
        "item_id": packet.payload.get("item_id"),
        "sensor": packet.payload,
    }
