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


def first_url(text: object) -> str:
    match = re.search(r"https?://[^\s'\"<>]+", str(text or ""))
    return match.group(0).rstrip("。；;") if match else ""


def extract_taobao_item_id(text: object) -> str:
    value = urllib.parse.unquote(str(text or ""))
    for pattern in [
        r"[?&]id=(\d{6,})",
        r"[?&]itemId=(\d{6,})",
        r"[?&]item_id=(\d{6,})",
        r"[?&]itemNumId=(\d{6,})",
        r"[?&]shareDetailItemId=(\d{6,})",
        r"/i(\d{6,})\.htm",
        r"item/(\d{6,})",
    ]:
        match = re.search(pattern, value, re.I)
        if match:
            return match.group(1)
    return ""


def resolve_taobao_link(source_url: str) -> dict:
    result = {
        "source_platform": "taobao",
        "source_url": source_url,
        "source_item_id": extract_taobao_item_id(source_url),
        "source_title": "",
        "target_url": "",
        "resolved_by": "gateway",
    }
    if not source_url:
        return result
    try:
        request = urllib.request.Request(
            source_url,
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        with LOCAL_OPENER.open(request, timeout=8) as response:
            html = response.read(700_000).decode("utf-8", "ignore")
        for pattern in [r"\burl\s*=\s*'([^']+)'", r'\burl\s*=\s*"([^"]+)"', r'"url"\s*:\s*"([^"]+)"']:
            match = re.search(pattern, html)
            if match:
                result["target_url"] = match.group(1).replace("\\/", "/")
                break
        result["source_item_id"] = result["source_item_id"] or extract_taobao_item_id(result["target_url"])
        title_match = re.search(r"「([^」]+)」", html)
        if title_match:
            result["source_title"] = title_match.group(1)[:120]
    except Exception as exc:
        result["warning"] = str(exc)[:240]
    return result


def color_to_bgr(value: object) -> tuple[int, int, int]:
    text = str(value or "").lower()
    if "蓝" in text or "blue" in text:
        return (218, 164, 92)
    if "酒红" in text or "紫" in text or "red" in text or "burgundy" in text:
        return (118, 52, 138)
    if "黑" in text or "black" in text:
        return (42, 43, 46)
    if "灰" in text or "gray" in text or "grey" in text:
        return (186, 188, 186) if "浅" in text or "light" in text else (105, 108, 110)
    if "白" in text or "米" in text or "white" in text:
        return (238, 237, 230)
    return (150, 150, 150)


def jpeg_data_url(image) -> str:
    import cv2  # type: ignore

    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        raise RuntimeError("failed to encode display card")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def create_catalog_card(payload: dict) -> str:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    name = str(payload.get("name") or payload.get("source_title") or "衣物")
    category = str(payload.get("category") or "").lower()
    color = color_to_bgr(payload.get("color") or name)
    dark = (72, 74, 78)
    white = (250, 250, 250)

    canvas = np.full((840, 720, 3), (249, 249, 251), dtype=np.uint8)
    shadow = np.zeros((840, 720), dtype=np.uint8)
    cv2.rectangle(shadow, (110, 115), (610, 720), 255, -1)
    shadow = cv2.GaussianBlur(shadow, (61, 61), 0)
    alpha = (shadow.astype("float32") / 255.0 * 0.11)[:, :, None]
    canvas[:] = (canvas.astype("float32") * (1 - alpha) + np.array((205, 207, 214), dtype="float32") * alpha).astype("uint8")

    if category == "bottom" or "裤" in name:
        left = np.array([[250, 160], [355, 160], [345, 720], [235, 720], [215, 300]], np.int32)
        right = np.array([[365, 160], [470, 160], [505, 720], [392, 720], [373, 300]], np.int32)
        cv2.fillPoly(canvas, [left, right], color)
        cv2.rectangle(canvas, (240, 145), (480, 190), dark, -1)
        cv2.line(canvas, (360, 190), (365, 720), (95, 95, 98), 5)
        cv2.line(canvas, (315, 155), (408, 155), (230, 190, 120), 6)
    elif category == "outer" or "外套" in name or "卫衣" in name:
        body = np.array([[250, 260], [470, 260], [585, 380], [535, 470], [490, 410], [490, 735], [230, 735], [230, 410], [185, 470], [135, 380]], np.int32)
        cv2.fillPoly(canvas, [body], color)
        cv2.ellipse(canvas, (360, 255), (105, 80), 0, 190, 350, color, -1)
        cv2.ellipse(canvas, (360, 265), (78, 54), 0, 190, 350, (235, 235, 235), 22)
        cv2.line(canvas, (360, 290), (360, 730), (95, 95, 98), 5)
        cv2.rectangle(canvas, (265, 530), (340, 600), (230, 230, 228), -1)
        cv2.rectangle(canvas, (382, 530), (457, 600), (230, 230, 228), -1)
    elif category == "shoes" or "鞋" in name:
        sole = np.array([[160, 520], [530, 520], [610, 565], [580, 615], [220, 615], [130, 575]], np.int32)
        upper = np.array([[190, 505], [275, 380], [440, 395], [560, 500], [525, 545], [215, 545]], np.int32)
        cv2.fillPoly(canvas, [sole], (118, 120, 124))
        cv2.fillPoly(canvas, [upper], color)
        cv2.rectangle(canvas, (205, 600), (575, 625), (222, 222, 218), -1)
        for x in [330, 370, 410]:
            cv2.circle(canvas, (x, 455), 10, (225, 225, 225), -1)
            cv2.line(canvas, (x - 24, 485), (x + 38, 455), (225, 225, 225), 5)
    else:
        body = np.array([[250, 185], [470, 185], [610, 320], [548, 420], [505, 355], [505, 725], [215, 725], [215, 355], [172, 420], [110, 320]], np.int32)
        cv2.fillPoly(canvas, [body], color)
        cv2.circle(canvas, (360, 205), 60, white, -1)
        cv2.rectangle(canvas, (285, 145), (435, 205), white, -1)
        if "polo" in name.lower() or "Polo" in name:
            cv2.line(canvas, (305, 210), (360, 285), white, 18)
            cv2.line(canvas, (415, 210), (360, 285), white, 18)
        else:
            cv2.ellipse(canvas, (360, 205), (75, 45), 0, 0, 180, dark, 12)
        if "球衣" in name or "jersey" in name.lower():
            cv2.circle(canvas, (470, 310), 34, white, -1)
            cv2.circle(canvas, (470, 310), 29, (210, 210, 210), 3)
            cv2.putText(canvas, "CITY", (300, 500), cv2.FONT_HERSHEY_SIMPLEX, 1.8, white, 6, cv2.LINE_AA)

    return jpeg_data_url(canvas)


def build_taobao_patch(payload: dict) -> dict:
    source_url = first_url(payload.get("source_url") or payload.get("taobao_url") or payload.get("url"))
    source = resolve_taobao_link(source_url) if source_url else {
        "source_platform": "taobao",
        "source_url": "",
        "source_item_id": "",
        "source_title": "",
        "resolved_by": "manual",
    }
    display_url = create_catalog_card({**payload, **source})
    patch = {
        "source_platform": "taobao",
        "source_url": source_url,
        "source_item_id": source.get("source_item_id", ""),
        "source_title": source.get("source_title", ""),
        "merchant_image_url": str(payload.get("merchant_image_url") or ""),
        "display_image_url": display_url,
        "display_image_path": "",
        "image_url": display_url,
        "image_path": "",
    }
    return {"ok": True, "source": source, "candidate_images": [], "selected_image": patch["merchant_image_url"], "patch": patch}


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
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/commerce/taobao/resolve":
            self.taobao_resolve()
            return
        if re.fullmatch(r"/api/clothes/\d+/taobao", path):
            self.taobao_update_item(int(path.strip("/").split("/")[-2]))
            return
        if path == "/__cloud/preprocess":
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

    def taobao_resolve(self) -> None:
        try:
            payload = self.read_json()
            self.send_json(build_taobao_patch(payload))
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def taobao_update_item(self, item_id: int) -> None:
        try:
            payload = self.read_json()
            result = build_taobao_patch(payload)
            current = self.board_json("GET", "/api/clothes").get("items", [])
            existing = next((item for item in current if int(item.get("id") or 0) == item_id), {})
            merged = {**existing, **payload, **result["patch"]}
            if merged.get("note"):
                merged["note"] = str(merged["note"])
            updated = self.board_json("PUT", f"/api/clothes/{item_id}", merged)
            item = updated.get("item", updated) if isinstance(updated, dict) else updated
            self.send_json({"item": item, **result})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def board_json(self, method: str, path: str, payload: dict | None = None) -> dict:
        target = urllib.parse.urljoin(self.board_url.rstrip("/") + "/", path.lstrip("/"))
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            target,
            data=body,
            headers={"Content-Type": "application/json"} if body is not None else {},
            method=method,
        )
        with LOCAL_OPENER.open(request, timeout=15) as response:
            raw = response.read().decode("utf-8-sig")
        return json.loads(raw) if raw.strip() else {}

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
