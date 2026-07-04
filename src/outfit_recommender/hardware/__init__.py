"""Hardware adapter layer for the smart wardrobe prototype."""

from .gy_as7341 import GYAS7341Reading, estimate_fabric_profile
from .imx179 import CameraScanEvent, create_scan_event
from .ss928 import SS928RecommendationService
from .ws63 import WS63SensorPacket, parse_ws63_packet

__all__ = [
    "CameraScanEvent",
    "GYAS7341Reading",
    "SS928RecommendationService",
    "WS63SensorPacket",
    "create_scan_event",
    "estimate_fabric_profile",
    "parse_ws63_packet",
]
