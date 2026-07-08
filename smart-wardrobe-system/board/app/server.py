#!/usr/bin/env python3
"""HTTP API server for the SS928 smart wardrobe MVP."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import pathlib
import platform
import socket
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from .core import (
    Camera,
    CloudPreprocessor,
    CloudSyncClient,
    ImageAnalyzer,
    RecommendationEngine,
    WardrobeDB,
    WeatherClient,
    crop_viewfinder_image,
    download_remote_image,
    make_display_image,
    make_merchant_display_image,
    merge_analysis_into_payload,
    save_ws63_payload,
    TaobaoResolver,
)


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
UPLOAD_ROOT = DATA_ROOT / "uploads"
MOBILE_ROOT = PROJECT_ROOT / "mobile-app"


class SmartWardrobeHandler(BaseHTTPRequestHandler):
    db: WardrobeDB
    weather: WeatherClient
    camera: Camera
    cloud_preprocessor: CloudPreprocessor
    cloud_sync: CloudSyncClient
    analyzer: ImageAnalyzer
    recommender: RecommendationEngine
    taobao: TaobaoResolver

    server_version = "SmartWardrobeHTTP/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            body = json.dumps(self.health_payload(), ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path in {"", "/"}:
            file_path = MOBILE_ROOT / "index.html"
        elif path.startswith("/uploads/"):
            file_path = UPLOAD_ROOT / path.removeprefix("/uploads/")
        else:
            file_path = MOBILE_ROOT / path.lstrip("/")
        self.send_file_headers(file_path)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/health":
                self.send_json(self.health_payload())
            elif path == "/api/cloud/sync/status":
                self.send_json(self.cloud_sync.status())
            elif path == "/api/clothes":
                self.ensure_display_images()
                self.send_json({"items": self.db.list_clothes(), "count": self.db.count()})
            elif path.startswith("/api/clothes/"):
                item_id = int(path.rsplit("/", 1)[-1])
                item = self.db.get_clothing(item_id)
                if not item:
                    self.send_json({"error": "clothing not found"}, HTTPStatus.NOT_FOUND)
                    return
                self.send_json({"item": item})
            elif path == "/api/camera/stream":
                self.serve_camera_stream()
            elif path == "/api/vision/cloud/status":
                self.send_json({"cloud": self.cloud_preprocessor.status()})
            elif path == "/api/ws63/latest":
                latest_path = DATA_ROOT / "ws63_latest.json"
                if not latest_path.exists():
                    self.send_json({"available": False}, HTTPStatus.NOT_FOUND)
                    return
                self.send_json({"available": True, "sensor": json.loads(latest_path.read_text(encoding="utf-8"))})
            elif path in {"/api/recommend", "/api/recommendations"}:
                city = query.get("city", [os.environ.get("SMART_WARDROBE_CITY", "Hangzhou")])[0]
                occasion = query.get("occasion", ["school"])[0]
                weather = self.weather.current_weather(city)
                result = self.recommender.recommend(
                    self.db.list_clothes(), weather, occasion=occasion, limit=3
                )
                self.send_json(result)
            elif path.startswith("/uploads/"):
                self.serve_file(UPLOAD_ROOT / path.removeprefix("/uploads/"))
            else:
                self.serve_mobile(path)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/clothes":
                payload = self.read_json()
                payload = self.apply_display_image(payload)
                item = self.db.add_clothing(payload)
                cloud_sync = self.cloud_sync.sync_item(item)
                self.send_json({"item": item, "cloud_sync": cloud_sync}, HTTPStatus.CREATED)
            elif path == "/api/clothes/capture":
                request_started = time.perf_counter()
                timings: Dict[str, int] = {}
                payload = self.read_json()
                use_viewfinder = bool(payload.pop("use_viewfinder", True))
                use_cloud_preprocess = bool(payload.pop("use_cloud_preprocess", True))
                stage_started = time.perf_counter()
                capture = self.camera.capture(
                    resolution=str(payload.pop("resolution", "640x480")),
                    skip_frames=int(payload.pop("skip_frames", 2)),
                )
                timings["capture_ms"] = int((time.perf_counter() - stage_started) * 1000)
                if use_viewfinder:
                    stage_started = time.perf_counter()
                    capture = self.apply_viewfinder_crop(capture)
                    timings["viewfinder_crop_ms"] = int((time.perf_counter() - stage_started) * 1000)
                if use_cloud_preprocess:
                    stage_started = time.perf_counter()
                    capture = self.apply_cloud_preprocess(capture)
                    timings["cloud_preprocess_ms"] = int((time.perf_counter() - stage_started) * 1000)
                payload.update(capture)
                if bool(payload.pop("auto_analyze", True)):
                    stage_started = time.perf_counter()
                    analysis = self.analyzer.analyze(
                        capture["image_path"], focus_viewfinder=False
                    )
                    timings["edge_analysis_ms"] = int((time.perf_counter() - stage_started) * 1000)
                    if capture.get("cloud_preprocess"):
                        analysis["cloud_preprocess"] = capture.get("cloud_preprocess")
                    payload = merge_analysis_into_payload(payload, analysis)
                payload = self.apply_display_image(payload)
                timings["total_ms"] = int((time.perf_counter() - request_started) * 1000)
                capture["timing_ms"] = timings
                item = self.db.add_clothing(payload)
                cloud_sync = self.cloud_sync.sync_item(item)
                self.send_json(
                    {
                        "item": item,
                        "capture": capture,
                        "analysis": item.get("ai_analysis", {}),
                        "timing_ms": timings,
                        "cloud_sync": cloud_sync,
                    },
                    HTTPStatus.CREATED,
                )
            elif path == "/api/clothes/capture/analyze":
                request_started = time.perf_counter()
                timings: Dict[str, int] = {}
                payload = self.read_json(allow_empty=True)
                use_viewfinder = bool(payload.pop("use_viewfinder", True))
                use_cloud_preprocess = bool(payload.pop("use_cloud_preprocess", True))
                stage_started = time.perf_counter()
                capture = self.camera.capture(
                    resolution=str(payload.pop("resolution", "640x480")),
                    skip_frames=int(payload.pop("skip_frames", 2)),
                )
                timings["capture_ms"] = int((time.perf_counter() - stage_started) * 1000)
                if use_viewfinder:
                    stage_started = time.perf_counter()
                    capture = self.apply_viewfinder_crop(capture)
                    timings["viewfinder_crop_ms"] = int((time.perf_counter() - stage_started) * 1000)
                if use_cloud_preprocess:
                    stage_started = time.perf_counter()
                    capture = self.apply_cloud_preprocess(capture)
                    timings["cloud_preprocess_ms"] = int((time.perf_counter() - stage_started) * 1000)
                stage_started = time.perf_counter()
                analysis = self.analyzer.analyze(
                    capture["image_path"], focus_viewfinder=False
                )
                timings["edge_analysis_ms"] = int((time.perf_counter() - stage_started) * 1000)
                if capture.get("cloud_preprocess"):
                    analysis["cloud_preprocess"] = capture.get("cloud_preprocess")
                payload.update(capture)
                draft = merge_analysis_into_payload(payload, analysis)
                draft = self.apply_display_image(draft)
                timings["total_ms"] = int((time.perf_counter() - request_started) * 1000)
                capture["timing_ms"] = timings
                self.send_json(
                    {
                        "draft": draft,
                        "capture": capture,
                        "analysis": analysis,
                        "timing_ms": timings,
                    }
                )
            elif path == "/api/demo/seed":
                payload = self.read_json(allow_empty=True)
                count = self.db.seed_demo_items(force=bool(payload.get("force", False)))
                self.send_json({"seeded": count, "count": self.db.count()})
            elif path == "/api/commerce/taobao/resolve":
                payload = self.read_json()
                result = self.resolve_taobao_payload(payload)
                self.send_json(result)
            elif path.startswith("/api/clothes/") and path.endswith("/taobao"):
                item_id = int(path.strip("/").split("/")[-2])
                existing = self.db.get_clothing(item_id)
                if not existing:
                    self.send_json({"error": "clothing not found"}, HTTPStatus.NOT_FOUND)
                    return
                result = self.resolve_taobao_payload(self.read_json(), base_item=existing)
                patch = result.get("patch", {})
                item = self.db.update_clothing(item_id, {**existing, **patch})
                cloud_sync = self.cloud_sync.sync_item(item) if item else {"ok": False}
                self.send_json({"item": item, "cloud_sync": cloud_sync, **result})
            elif path == "/api/cloud/sync":
                payload = self.read_json(allow_empty=True)
                items = self.db.list_clothes()
                if payload.get("id") is not None:
                    requested = {str(payload.get("id"))}
                    items = [item for item in items if str(item.get("id")) in requested]
                elif payload.get("ids"):
                    requested = {str(item_id) for item_id in payload.get("ids") or []}
                    items = [item for item in items if str(item.get("id")) in requested]
                self.send_json(self.cloud_sync.sync_items(items))
            elif path == "/api/ws63/sensor":
                payload = self.read_json()
                saved = save_ws63_payload(DATA_ROOT / "ws63_latest.json", payload)
                self.send_json({"sensor": saved})
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def apply_viewfinder_crop(self, capture: Dict[str, Any]) -> Dict[str, Any]:
        cropped = crop_viewfinder_image(capture["image_path"], UPLOAD_ROOT)
        if not cropped:
            return capture
        updated = dict(capture)
        updated["raw_image_path"] = capture.get("image_path", "")
        updated["raw_image_url"] = capture.get("image_url", "")
        updated.update(cropped)
        updated["crop_applied"] = True
        return updated

    def apply_cloud_preprocess(self, capture: Dict[str, Any]) -> Dict[str, Any]:
        source_path = capture.get("image_path", "")
        if not source_path:
            return capture
        cloud = self.cloud_preprocessor.preprocess(
            source_path,
            image_url=str(capture.get("image_url") or ""),
        )
        updated = dict(capture)
        updated["cloud_preprocess"] = cloud
        if not cloud.get("ok"):
            return updated
        updated["pre_cloud_image_path"] = capture.get("image_path", "")
        updated["pre_cloud_image_url"] = capture.get("image_url", "")
        updated.update(
            {
                "image_path": cloud.get("image_path", capture.get("image_path", "")),
                "image_url": cloud.get("image_url", capture.get("image_url", "")),
                "cloud_crop_applied": True,
            }
        )
        return updated

    def apply_display_image(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = self.apply_merchant_image(payload)
        image_path = str(payload.get("image_path") or "").strip()
        if not image_path or payload.get("display_image_url"):
            return payload
        display = make_display_image(
            image_path,
            UPLOAD_ROOT,
            category=payload.get("category", ""),
            color=payload.get("color", ""),
            name=payload.get("name", ""),
        )
        if not display:
            return payload
        updated = dict(payload)
        updated.update(display)
        return updated

    def apply_merchant_image(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if payload.get("display_image_url"):
            return payload
        image_path = str(payload.get("merchant_image_path") or "").strip()
        if not image_path and payload.get("merchant_image_url"):
            prefix = str(payload.get("source_item_id") or payload.get("name") or "merchant")
            try:
                downloaded = download_remote_image(str(payload.get("merchant_image_url")), UPLOAD_ROOT, prefix=prefix)
            except Exception as exc:
                updated = dict(payload)
                updated["commerce_warning"] = str(exc)
                return updated
            updated = dict(payload)
            updated.update(downloaded)
            payload = updated
            image_path = str(payload.get("merchant_image_path") or payload.get("image_path") or "").strip()
        if not image_path:
            return payload
        display = make_merchant_display_image(
            image_path,
            UPLOAD_ROOT,
            name=payload.get("name", ""),
        )
        if not display:
            return payload
        updated = dict(payload)
        updated.update(display)
        return updated

    def resolve_taobao_payload(self, payload: Dict[str, Any], base_item: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        source_url = str(payload.get("source_url") or payload.get("taobao_url") or payload.get("url") or "").strip()
        merchant_image_url = str(payload.get("merchant_image_url") or payload.get("image_url") or "").strip()
        if not source_url and not merchant_image_url:
            raise ValueError("taobao link or merchant image url is required")
        source = self.taobao.resolve(source_url) if source_url else {
            "source_platform": "taobao",
            "source_url": "",
            "source_item_id": "",
            "source_title": "",
            "candidate_images": [],
            "resolved_by": "merchant_image_url",
        }
        candidate_images = list(source.get("candidate_images") or [])
        selected_image = merchant_image_url or (candidate_images[0] if candidate_images else "")
        patch: Dict[str, Any] = {
            "source_platform": "taobao",
            "source_url": source_url or str(source.get("source_url") or ""),
            "source_item_id": str(source.get("source_item_id") or ""),
            "source_title": str(source.get("source_title") or ""),
            "merchant_image_url": selected_image,
        }
        if not patch["source_title"] and base_item:
            patch["source_title"] = str(base_item.get("name") or "")
        if selected_image:
            temp_payload = {
                **(base_item or {}),
                **payload,
                **patch,
                "name": payload.get("name") or (base_item or {}).get("name") or patch["source_title"],
                "display_image_url": "",
                "display_image_path": "",
            }
            patch.update(self.apply_merchant_image(temp_payload))
        result = {
            "source": source,
            "candidate_images": candidate_images,
            "selected_image": selected_image,
            "patch": patch,
        }
        if selected_image:
            result["ok"] = bool(patch.get("display_image_url"))
        else:
            result["ok"] = False
            result["message"] = "Taobao link was parsed, but no merchant image was available without Open Platform API; paste a merchant image URL to create the display card."
        return result

    def ensure_display_images(self) -> None:
        for item in self.db.list_clothes():
            if item.get("display_image_url") or not item.get("image_path"):
                continue
            display = make_display_image(
                str(item.get("image_path")),
                UPLOAD_ROOT,
                category=item.get("category", ""),
                color=item.get("color", ""),
                name=item.get("name", ""),
            )
            if not display:
                continue
            payload = dict(item)
            payload.update(display)
            self.db.update_clothing(int(item["id"]), payload)

    def do_PUT(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/clothes/"):
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            item_id = int(path.rsplit("/", 1)[-1])
            item = self.db.update_clothing(item_id, self.apply_display_image(self.read_json()))
            if not item:
                self.send_json({"error": "clothing not found"}, HTTPStatus.NOT_FOUND)
                return
            cloud_sync = self.cloud_sync.sync_item(item)
            self.send_json({"item": item, "cloud_sync": cloud_sync})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/clothes/"):
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            item_id = int(path.rsplit("/", 1)[-1])
            deleted = self.db.delete_clothing(item_id)
            self.send_json({"deleted": deleted}, HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def read_json(self, allow_empty: bool = False) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length == 0:
            if allow_empty:
                return {}
            raise ValueError("empty request body")
        body = self.rfile.read(length)
        if not body.strip() and allow_empty:
            return {}
        return json.loads(body.decode("utf-8"))

    def send_json(self, payload: Dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_mobile(self, path: str) -> None:
        if path in {"", "/"}:
            file_path = MOBILE_ROOT / "index.html"
        else:
            file_path = MOBILE_ROOT / path.lstrip("/")
        self.serve_file(file_path, root=MOBILE_ROOT)

    def serve_file(self, file_path: pathlib.Path, root: Optional[pathlib.Path] = None) -> None:
        file_path = file_path.resolve()
        root = (root or UPLOAD_ROOT).resolve()
        if root not in file_path.parents and file_path != root:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_camera_stream(self) -> None:
        boundary = "smartwardrobe"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=%s" % boundary)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.end_headers()
        while True:
            jpeg = self.camera.latest_jpeg(max_age=5.0)
            if not jpeg:
                time.sleep(0.15)
                continue
            try:
                self.wfile.write(("--%s\r\n" % boundary).encode("ascii"))
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(("Content-Length: %d\r\n\r\n" % len(jpeg)).encode("ascii"))
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
                time.sleep(0.16)
            except (BrokenPipeError, ConnectionResetError):
                break

    def send_file_headers(self, file_path: pathlib.Path, root: Optional[pathlib.Path] = None) -> None:
        file_path = file_path.resolve()
        root = (root or (UPLOAD_ROOT if str(file_path).startswith(str(UPLOAD_ROOT.resolve())) else MOBILE_ROOT)).resolve()
        if root not in file_path.parents and file_path != root:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.end_headers()

    def health_payload(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "hostname": socket.gethostname(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "db_path": str(self.db.db_path),
            "clothes_count": self.db.count(),
            "camera": {
                "device": self.camera.device,
                "available": self.camera.available(),
                "live": bool(self.camera.latest_jpeg(max_age=5.0)),
                "stream_error": self.camera.stream_error(),
            },
            "vision": {
                "opencv_required": True,
                "mode": "cloud_subject_crop_plus_edge_model",
                "cloud": self.cloud_preprocessor.status(),
            },
        }


def make_handler(db_path: pathlib.Path, camera_device: str) -> type[SmartWardrobeHandler]:
    SmartWardrobeHandler.db = WardrobeDB(db_path)
    SmartWardrobeHandler.weather = WeatherClient(DATA_ROOT / "weather_cache.json")
    SmartWardrobeHandler.camera = Camera(UPLOAD_ROOT, device=camera_device)
    SmartWardrobeHandler.camera.start_live()
    SmartWardrobeHandler.cloud_preprocessor = CloudPreprocessor(UPLOAD_ROOT)
    SmartWardrobeHandler.cloud_sync = CloudSyncClient()
    SmartWardrobeHandler.analyzer = ImageAnalyzer()
    SmartWardrobeHandler.recommender = RecommendationEngine()
    SmartWardrobeHandler.taobao = TaobaoResolver()
    return SmartWardrobeHandler


def serve_forever(httpd: ThreadingHTTPServer, label: str) -> None:
    print("Smart wardrobe server listening on %s" % label, flush=True)
    httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SMART_WARDROBE_PORT", "8000")))
    parser.add_argument("--also-port", type=int, default=0)
    parser.add_argument("--db", default=os.environ.get("SMART_WARDROBE_DB", str(DATA_ROOT / "wardrobe.db")))
    parser.add_argument("--camera", default=os.environ.get("SMART_WARDROBE_CAMERA", "/dev/video0"))
    parser.add_argument("--seed", action="store_true", help="Insert demo clothes if the database is empty.")
    args = parser.parse_args()

    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    handler = make_handler(pathlib.Path(args.db), args.camera)
    if args.seed:
        count = handler.db.seed_demo_items(force=False)
        if count:
            print("Seeded %d demo clothes." % count)
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    servers = [(httpd, "http://%s:%d" % (args.host, args.port))]
    if args.also_port and args.also_port != args.port:
        also = ThreadingHTTPServer((args.host, args.also_port), handler)
        servers.append((also, "http://%s:%d" % (args.host, args.also_port)))
    print("Open from PC/tablet: http://192.168.137.2:%d" % args.port, flush=True)
    if args.also_port:
        print("Tablet-friendly URL: http://192.168.137.2", flush=True)
    threads = []
    for server, label in servers[1:]:
        thread = threading.Thread(target=serve_forever, args=(server, label), daemon=True)
        thread.start()
        threads.append(thread)
    serve_forever(servers[0][0], servers[0][1])


if __name__ == "__main__":
    main()
