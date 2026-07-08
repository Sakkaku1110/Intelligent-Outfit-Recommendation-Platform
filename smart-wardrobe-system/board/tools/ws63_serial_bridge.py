#!/usr/bin/env python3
"""Bridge WS63 serial AS7341 packets into the SS928 backend."""

from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import select
import sys
import termios
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Optional


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.nearlink_frame import FRAME_SIZE, MAGIC, decode_spectral_frame  # noqa: E402


BAUD_RATES = {
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
    230400: getattr(termios, "B230400", termios.B115200),
    460800: getattr(termios, "B460800", termios.B115200),
    921600: getattr(termios, "B921600", termios.B115200),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read WS63 serial AS7341 packets and post them to SS928 backend.")
    parser.add_argument("--port", default=os.environ.get("SMART_WARDROBE_WS63_SERIAL", "auto"))
    parser.add_argument("--baud", type=int, default=int(os.environ.get("SMART_WARDROBE_WS63_BAUD", "115200")))
    parser.add_argument("--post-to", default=os.environ.get("SMART_WARDROBE_WS63_POST_URL", "http://127.0.0.1:8000/api/ws63/sensor"))
    parser.add_argument("--scan-interval", type=float, default=2.0)
    parser.add_argument("--read-timeout", type=float, default=0.5)
    parser.add_argument("--idle-rescan", type=float, default=float(os.environ.get("SMART_WARDROBE_WS63_IDLE_RESCAN", "15")))
    return parser.parse_args()


def candidate_ports() -> List[str]:
    ports: List[str] = []
    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyAMA*", "/dev/ttyS*"):
        ports.extend(glob.glob(pattern))
    filtered = []
    for port in sorted(set(ports)):
        name = pathlib.Path(port).name
        if name in {"ttyAMA0", "ttyS0"}:
            continue
        filtered.append(port)
    return filtered


def resolve_port(requested: str) -> Optional[str]:
    if requested and requested != "auto":
        return requested if pathlib.Path(requested).exists() else None
    ports = candidate_ports()
    return ports[0] if ports else None


def open_serial(port: str, baud: int) -> int:
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    baud_value = BAUD_RATES.get(baud)
    if baud_value is None:
        os.close(fd)
        raise ValueError("unsupported baud rate: %s" % baud)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CLOCAL | termios.CREAD | termios.CS8
    attrs[3] = 0
    attrs[4] = baud_value
    attrs[5] = baud_value
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 5
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def post_json(url: str, payload: Dict[str, Any]) -> bool:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
        return True
    except urllib.error.URLError as exc:
        print("[ws63] POST failed: %s" % exc, flush=True)
        return False


def parse_json_line(line: bytes) -> Optional[Dict[str, Any]]:
    text = line.decode("utf-8", errors="ignore").strip()
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        print("[ws63] raw: %s" % text[:160], flush=True)
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        print("[ws63] non-json: %s" % text[:160], flush=True)
        return None
    if not isinstance(payload, dict):
        payload = {"value": payload}
    payload.setdefault("device", "WS63")
    payload.setdefault("sensor", "GY-AS7341")
    payload.setdefault("transport", "serial_json")
    return payload


class StreamParser:
    def __init__(self) -> None:
        self.line_buffer = bytearray()
        self.binary_buffer = bytearray()

    def feed(self, chunk: bytes) -> Iterable[Dict[str, Any]]:
        self.binary_buffer.extend(chunk)
        while True:
            start = self.binary_buffer.find(MAGIC)
            if start < 0:
                keep = len(MAGIC) - 1
                if len(self.binary_buffer) > keep:
                    del self.binary_buffer[:-keep]
                break
            if start:
                del self.binary_buffer[:start]
            if len(self.binary_buffer) < FRAME_SIZE:
                break
            candidate = bytes(self.binary_buffer[:FRAME_SIZE])
            del self.binary_buffer[:FRAME_SIZE]
            try:
                yield decode_spectral_frame(candidate).to_payload()
            except Exception as exc:
                print("[ws63] bad binary frame: %s" % exc, flush=True)

        self.line_buffer.extend(chunk)
        while b"\n" in self.line_buffer:
            line, _, rest = self.line_buffer.partition(b"\n")
            self.line_buffer = bytearray(rest)
            payload = parse_json_line(line)
            if payload is not None:
                yield payload
        if len(self.line_buffer) > 4096:
            del self.line_buffer[:-512]


def run_bridge(args: argparse.Namespace) -> None:
    parser = StreamParser()
    while True:
        port = resolve_port(args.port)
        if not port:
            print("[ws63] no serial port found; waiting. candidates=%s" % candidate_ports(), flush=True)
            time.sleep(args.scan_interval)
            continue
        try:
            print("[ws63] opening %s @ %s" % (port, args.baud), flush=True)
            fd = open_serial(port, args.baud)
        except Exception as exc:
            print("[ws63] open failed for %s: %s" % (port, exc), flush=True)
            time.sleep(args.scan_interval)
            continue
        try:
            last_data = time.monotonic()
            while True:
                ready, _, _ = select.select([fd], [], [], args.read_timeout)
                if not ready:
                    if args.port == "auto" and time.monotonic() - last_data > args.idle_rescan:
                        better = resolve_port(args.port)
                        if better and better != port:
                            print("[ws63] switching serial port %s -> %s" % (port, better), flush=True)
                            break
                        last_data = time.monotonic()
                    continue
                chunk = os.read(fd, 1024)
                if not chunk:
                    time.sleep(0.05)
                    continue
                last_data = time.monotonic()
                for payload in parser.feed(chunk):
                    ok = post_json(args.post_to, payload)
                    print("[ws63] packet seq=%s posted=%s" % (payload.get("seq", ""), ok), flush=True)
        except OSError as exc:
            print("[ws63] serial read failed: %s" % exc, flush=True)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            time.sleep(args.scan_interval)


def main() -> None:
    run_bridge(parse_args())


if __name__ == "__main__":
    main()
