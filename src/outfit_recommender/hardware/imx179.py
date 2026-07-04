from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class CameraScanEvent:
    event_id: str
    direction: str
    image_path: str | None
    timestamp: str


def create_scan_event(
    direction: str,
    image_path: str | None = None,
    event_id: str | None = None,
) -> CameraScanEvent:
    if direction not in {"in", "out"}:
        raise ValueError("direction must be 'in' or 'out'")
    now = datetime.now(timezone.utc).isoformat()
    return CameraScanEvent(
        event_id=event_id or f"scan-{now}",
        direction=direction,
        image_path=image_path,
        timestamp=now,
    )
