#!/usr/bin/env python3
"""Read WS63 serial output and optionally forward JSON packets to the backend."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


DEFAULT_PORT = "/dev/cu.wchusbserial130"
DEFAULT_BAUD = 115200


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe a WS63 serial port. Plain text is printed as-is; newline-delimited "
            "JSON can be forwarded to /api/ws63/sensor."
        )
    )
    parser.add_argument(
        "--port",
        "--serial",
        default=DEFAULT_PORT,
        help=f"Serial port path, for example {DEFAULT_PORT} on macOS or /dev/ttyUSB0 on Linux.",
    )
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help="Serial baud rate.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Serial read timeout in seconds.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Only print raw serial lines without JSON formatting.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit after the first non-empty line.",
    )
    parser.add_argument(
        "--post-to",
        help=(
            "Forward parsed JSON packets to a backend endpoint, for example "
            "http://127.0.0.1:8000/api/ws63/sensor."
        ),
    )
    parser.add_argument(
        "--write",
        help="Send one command to WS63 immediately after opening the serial port.",
    )
    parser.add_argument(
        "--no-newline",
        action="store_true",
        help="Do not append a newline when using --write.",
    )
    return parser.parse_args()


def load_serial_module() -> Any:
    try:
        import serial  # type: ignore
    except ImportError:
        print(
            "pyserial is not installed. Run: pip install pyserial",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return serial


def decode_line(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip()


def parse_json_line(text: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def post_json(url: str, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"[POST {response.status}] {body}")
    except urllib.error.URLError as exc:
        print(f"[POST failed] {exc}", file=sys.stderr)


def print_packet(text: str, payload: Optional[Dict[str, Any]], raw_only: bool) -> None:
    timestamp = time.strftime("%H:%M:%S")
    if raw_only or payload is None:
        print(f"[{timestamp}] {text}")
        return
    print(f"[{timestamp}] JSON")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def read_serial(args: argparse.Namespace) -> None:
    serial = load_serial_module()

    print(f"Opening {args.port} at {args.baud} baud. Press Ctrl+C to stop.")
    with serial.Serial(args.port, baudrate=args.baud, timeout=args.timeout) as connection:
        if args.write:
            command = args.write if args.no_newline else args.write + "\n"
            connection.write(command.encode("utf-8"))
            connection.flush()
            print(f"Sent: {args.write!r}")

        while True:
            raw = connection.readline()
            if not raw:
                continue

            text = decode_line(raw)
            if not text:
                continue

            payload = parse_json_line(text)
            print_packet(text, payload, args.raw)

            if args.post_to and payload is not None:
                post_json(args.post_to, payload)
            elif args.post_to and payload is None:
                print("[skip POST] line is not valid JSON")

            if args.once:
                break


def main() -> None:
    args = parse_args()
    try:
        read_serial(args)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
