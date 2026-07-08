"""NearLink spectral frame codec for WS63 -> SS928 packets.

The transport layer can be real NearLink, a serial debug bridge, or a file
replay. This module only owns the binary frame format and converts frames into
the AS7341 payload shape consumed by spectral_material.py.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


MAGIC = b"SWSP"
VERSION = 1
MSG_AS7341_READING = 1
CHANNEL_NAMES = ("f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "clear", "nir")

_HEADER = struct.Struct("<4sBBHIII")
_TAIL = struct.Struct("<10HBHHB")
CRC_SIZE = 2
FRAME_SIZE = _HEADER.size + _TAIL.size + CRC_SIZE
PAYLOAD_SIZE = _TAIL.size


class NearLinkFrameError(ValueError):
    """Raised when a NearLink frame is malformed or fails checksum validation."""


@dataclass(frozen=True)
class SpectralFrame:
    device_id: int
    seq: int
    timestamp_ms: int
    channels: Dict[str, int]
    gain: int = 8
    atime: int = 99
    astep: int = 999
    flags: int = 0

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "device": "WS63",
            "sensor": "GY-AS7341",
            "transport": "nearlink",
            "device_id": self.device_id,
            "seq": self.seq,
            "timestamp_ms": self.timestamp_ms,
            "gain": self.gain,
            "atime": self.atime,
            "astep": self.astep,
            "flags": self.flags,
        }
        payload.update(self.channels)
        return payload


def encode_spectral_frame(frame: SpectralFrame) -> bytes:
    channel_values = [_uint16(frame.channels[name], name) for name in CHANNEL_NAMES]
    header = _HEADER.pack(
        MAGIC,
        VERSION,
        MSG_AS7341_READING,
        PAYLOAD_SIZE,
        _uint32(frame.device_id, "device_id"),
        _uint32(frame.seq, "seq"),
        _uint32(frame.timestamp_ms, "timestamp_ms"),
    )
    tail = _TAIL.pack(
        *channel_values,
        _uint8(frame.gain, "gain"),
        _uint16(frame.atime, "atime"),
        _uint16(frame.astep, "astep"),
        _uint8(frame.flags, "flags"),
    )
    body = header + tail
    return body + struct.pack("<H", crc16_ccitt(body))


def decode_spectral_frame(data: bytes) -> SpectralFrame:
    if len(data) != FRAME_SIZE:
        raise NearLinkFrameError("expected %d bytes, got %d" % (FRAME_SIZE, len(data)))

    expected_crc = struct.unpack_from("<H", data, FRAME_SIZE - CRC_SIZE)[0]
    actual_crc = crc16_ccitt(data[:-CRC_SIZE])
    if expected_crc != actual_crc:
        raise NearLinkFrameError(
            "CRC mismatch: expected 0x%04x, calculated 0x%04x"
            % (expected_crc, actual_crc)
        )

    magic, version, msg_type, payload_len, device_id, seq, timestamp_ms = _HEADER.unpack_from(data)
    if magic != MAGIC:
        raise NearLinkFrameError("invalid magic: %r" % (magic,))
    if version != VERSION:
        raise NearLinkFrameError("unsupported version: %d" % version)
    if msg_type != MSG_AS7341_READING:
        raise NearLinkFrameError("unsupported message type: %d" % msg_type)
    if payload_len != PAYLOAD_SIZE:
        raise NearLinkFrameError("invalid payload length: %d" % payload_len)

    tail = _TAIL.unpack_from(data, _HEADER.size)
    channel_values = tail[: len(CHANNEL_NAMES)]
    gain, atime, astep, flags = tail[len(CHANNEL_NAMES) :]
    channels = dict(zip(CHANNEL_NAMES, channel_values))
    return SpectralFrame(
        device_id=device_id,
        seq=seq,
        timestamp_ms=timestamp_ms,
        channels=channels,
        gain=gain,
        atime=atime,
        astep=astep,
        flags=flags,
    )


def iter_spectral_frames(chunks: Iterable[bytes]) -> Iterable[SpectralFrame]:
    """Yield valid frames from an arbitrary byte stream.

    Bad frames are skipped after the magic marker. The caller can keep the stream
    alive even if one packet is truncated or corrupted.
    """

    buffer = bytearray()
    for chunk in chunks:
        if not chunk:
            continue
        buffer.extend(chunk)

        while True:
            start = buffer.find(MAGIC)
            if start < 0:
                keep = len(MAGIC) - 1
                if len(buffer) > keep:
                    del buffer[:-keep]
                break
            if start:
                del buffer[:start]
            if len(buffer) < FRAME_SIZE:
                break

            candidate = bytes(buffer[:FRAME_SIZE])
            del buffer[:FRAME_SIZE]
            try:
                yield decode_spectral_frame(candidate)
            except NearLinkFrameError:
                continue


def payload_from_frame(data: bytes) -> Dict[str, Any]:
    return decode_spectral_frame(data).to_payload()


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _uint8(value: int, name: str) -> int:
    if not 0 <= int(value) <= 0xFF:
        raise ValueError("%s out of uint8 range: %r" % (name, value))
    return int(value)


def _uint16(value: int, name: str) -> int:
    if not 0 <= int(value) <= 0xFFFF:
        raise ValueError("%s out of uint16 range: %r" % (name, value))
    return int(value)


def _uint32(value: int, name: str) -> int:
    if not 0 <= int(value) <= 0xFFFFFFFF:
        raise ValueError("%s out of uint32 range: %r" % (name, value))
    return int(value)
