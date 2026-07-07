#!/usr/bin/env python3
"""Windows-side gateway for tablets and phones.

Other devices connect to this PC, and the gateway proxies requests to the
SS928 board. This avoids routing issues caused by Windows ICS or separated
Wi-Fi/Ethernet subnets.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class GatewayHandler(BaseHTTPRequestHandler):
    board_url = "http://192.168.137.2:8000"
    gemini_api_key = ""
    gemini_model = "gemini-2.5-flash"
    gemini_timeout = 4.2
    mobile_root = pathlib.Path(__file__).resolve().parent / "mobile-app"

    def log_message(self, fmt: str, *args: object) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS,HEAD")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_HEAD(self) -> None:
        if self.should_serve_local():
            self.serve_local(write_body=False)
            return
        self.proxy(write_body=False)

    def do_GET(self) -> None:
        if self.path == "/__gateway":
            self.send_gateway_health()
            return
        if self.should_serve_local():
            self.serve_local(write_body=True)
            return
        self.proxy(write_body=True)

    def do_POST(self) -> None:
        if urllib.parse.urlparse(self.path).path == "/__cloud/preprocess":
            self.cloud_preprocess()
            return
        self.proxy(write_body=True)

    def do_PUT(self) -> None:
        self.proxy(write_body=True)

    def do_DELETE(self) -> None:
        self.proxy(write_body=True)

    def send_gateway_health(self) -> None:
        body = (
            "{\n"
            '  "status": "ok",\n'
            f'  "board_url": "{self.board_url}"\n'
            f'  ,"cloud_configured": {str(bool(self.gemini_api_key)).lower()}\n'
            f'  ,"cloud_timeout_sec": {self.gemini_timeout}\n'
            "}\n"
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def should_serve_local(self) -> bool:
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/") or path.startswith("/uploads/") or path.startswith("/__cloud/"):
            return False
        return self.command in {"GET", "HEAD"}

    def serve_local(self, write_body: bool) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path in {"", "/"}:
            file_path = self.mobile_root / "index.html"
        else:
            file_path = self.mobile_root / path.lstrip("/")
        try:
            resolved = file_path.resolve()
            root = self.mobile_root.resolve()
            if root not in resolved.parents and resolved != root:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not resolved.exists() or not resolved.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            body = resolved.read_bytes() if write_body else b""
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(resolved.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if write_body:
                self.wfile.write(body)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def proxy(self, write_body: bool) -> None:
        target = urllib.parse.urljoin(self.board_url.rstrip("/") + "/", self.path.lstrip("/"))
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length) if length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP and key.lower() != "host"
        }
        headers["Connection"] = "close"
        request = urllib.request.Request(target, data=body, headers=headers, method=self.command)
        try:
            with LOCAL_OPENER.open(request, timeout=15) as response:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in HOP_BY_HOP:
                        self.send_header(key, value)
                self.end_headers()
                if not write_body:
                    return
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                if key.lower() not in HOP_BY_HOP:
                    self.send_header(key, value)
            self.end_headers()
            if write_body:
                self.wfile.write(exc.read())
        except Exception as exc:
            body = ("Gateway cannot reach board: %s\n" % exc).encode("utf-8")
            self.send_response(HTTPStatus.BAD_GATEWAY)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if write_body:
                self.wfile.write(body)

    def cloud_preprocess(self) -> None:
        started = time.perf_counter()
        try:
            payload = self.read_json()
            if not self.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is not configured on PC gateway")
            result = self.call_gemini(payload)
            result["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
            self.send_json(result)
        except Exception as exc:
            print("Cloud proxy error: %s" % exc, flush=True)
            self.send_json(
                {
                    "ok": False,
                    "reason": "cloud_proxy_error",
                    "message": str(exc)[:500],
                    "elapsed_ms": int((time.perf_counter() - started) * 1000),
                },
                HTTPStatus.OK,
            )

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8-sig"))

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def call_gemini(self, payload: dict) -> dict:
        image_data = str(payload.get("image_data") or "")
        if not image_data:
            raise ValueError("image_data is required")
        # Validate base64 early so malformed payloads fail before hitting Gemini.
        base64.b64decode(image_data, validate=True)
        mime_type = str(payload.get("mime_type") or "image/jpeg")
        model = str(payload.get("model") or self.gemini_model)
        timeout = float(payload.get("timeout_sec") or self.gemini_timeout)
        prompt = (
            "Find the single main clothing item that should be stored in a smart wardrobe dataset. "
            "Ignore hands, hangers, faces, shoes worn by people, background furniture, curtains, beds, desks, and other clutter. "
            "Return only valid JSON with this schema: "
            "{\"box_2d\":[ymin,xmin,ymax,xmax],\"label\":\"garment\",\"confidence\":0.0,\"quality\":\"ok|bad\",\"reason\":\"short\"}. "
            "Coordinates must be normalized integers from 0 to 1000 relative to the full image. "
            "If no garment is visible, set confidence to 0 and box_2d to [0,0,1000,1000]."
        )
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": image_data}},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.05,
                "maxOutputTokens": 180,
                "responseMimeType": "application/json",
            },
        }
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + urllib.parse.quote(model, safe="-_.")
            + ":generateContent?key="
            + urllib.parse.quote(self.gemini_api_key)
        )
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            gemini = json.loads(response.read().decode("utf-8"))
        text = self.gemini_text(gemini)
        parsed = self.parse_json_object(text)
        box = self.normalized_box(parsed.get("box_2d"))
        return {
            "ok": True,
            "provider": "gemini_pc_proxy",
            "model": model,
            "label": str(parsed.get("label") or "garment"),
            "confidence": float(parsed.get("confidence") or 0),
            "quality": str(parsed.get("quality") or "ok"),
            "reason": str(parsed.get("reason") or "")[:240],
            "normalized_box": box,
        }

    def gemini_text(self, payload: dict) -> str:
        candidates = payload.get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        text = "\n".join(str(part.get("text") or "") for part in parts if part.get("text"))
        if not text.strip():
            raise RuntimeError("Gemini returned empty text")
        return text

    def parse_json_object(self, text: str) -> dict:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        if not cleaned.startswith("{"):
            match = re.search(r"\{.*\}", cleaned, flags=re.S)
            if match:
                cleaned = match.group(0)
        data = json.loads(cleaned)
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            raise ValueError("Gemini JSON is not an object")
        return data

    def normalized_box(self, value: object) -> list[int]:
        if not isinstance(value, list) or len(value) != 4:
            return [0, 0, 1000, 1000]
        numbers = []
        for item in value:
            try:
                numbers.append(int(round(float(item))))
            except (TypeError, ValueError):
                numbers.append(0)
        y1, x1, y2, x2 = [max(0, min(1000, number)) for number in numbers]
        if y2 <= y1 + 20 or x2 <= x1 + 20:
            return [0, 0, 1000, 1000]
        return [y1, x1, y2, x2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--board", default="http://192.168.137.2:8000")
    args = parser.parse_args()

    GatewayHandler.board_url = args.board
    GatewayHandler.gemini_api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("SMART_WARDROBE_GEMINI_API_KEY")
        or ""
    ).strip()
    GatewayHandler.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    GatewayHandler.gemini_timeout = float(os.environ.get("SMART_WARDROBE_GEMINI_TIMEOUT", "4.2") or 4.2)
    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print("Smart wardrobe PC gateway listening on http://%s:%d" % (args.host, args.port), flush=True)
    print("Proxying board:", args.board, flush=True)
    print("Cloud proxy configured:", bool(GatewayHandler.gemini_api_key), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
