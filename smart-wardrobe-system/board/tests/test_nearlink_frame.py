from __future__ import annotations

import pytest

from board.app.nearlink_frame import (
    FRAME_SIZE,
    NearLinkFrameError,
    SpectralFrame,
    decode_spectral_frame,
    encode_spectral_frame,
    iter_spectral_frames,
)
from board.app.spectral_material import classify_material


def sample_frame() -> SpectralFrame:
    return SpectralFrame(
        device_id=0x6301,
        seq=42,
        timestamp_ms=123456,
        channels={
            "f1": 120,
            "f2": 130,
            "f3": 160,
            "f4": 190,
            "f5": 210,
            "f6": 230,
            "f7": 240,
            "f8": 250,
            "clear": 640,
            "nir": 110,
        },
    )


def test_round_trip_spectral_frame() -> None:
    encoded = encode_spectral_frame(sample_frame())

    assert len(encoded) == FRAME_SIZE
    decoded = decode_spectral_frame(encoded)
    assert decoded == sample_frame()
    assert decoded.to_payload()["transport"] == "nearlink"


def test_crc_rejects_corrupt_frame() -> None:
    encoded = bytearray(encode_spectral_frame(sample_frame()))
    encoded[20] ^= 0x01

    with pytest.raises(NearLinkFrameError):
        decode_spectral_frame(bytes(encoded))


def test_stream_parser_skips_noise_and_classifies_payload() -> None:
    encoded = encode_spectral_frame(sample_frame())
    frames = list(iter_spectral_frames([b"noise", encoded[:13], encoded[13:]]))

    assert len(frames) == 1
    payload = frames[0].to_payload()
    result = classify_material(payload)
    assert result["sensor"] == "GY-AS7341"
    assert result["quality"] == "ok"
