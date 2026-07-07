#!/usr/bin/env python3
"""Core logic for the SS928 smart wardrobe MVP.

The code intentionally avoids heavy third-party dependencies so it can run on
the HiEulerPI/SS928 board with only Python 3 and a few small Linux tools.
"""

from __future__ import annotations

import base64
import itertools
import json
import os
import pathlib
import re
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


CATEGORY_ALIASES = {
    "top": "top",
    "shirt": "top",
    "tshirt": "top",
    "tee": "top",
    "上衣": "top",
    "短袖": "top",
    "衬衫": "top",
    "卫衣": "top",
    "bottom": "bottom",
    "pants": "bottom",
    "trousers": "bottom",
    "skirt": "bottom",
    "下装": "bottom",
    "裤子": "bottom",
    "长裤": "bottom",
    "短裤": "bottom",
    "裙子": "bottom",
    "outer": "outer",
    "coat": "outer",
    "jacket": "outer",
    "外套": "outer",
    "羽绒服": "outer",
    "夹克": "outer",
    "shoes": "shoes",
    "shoe": "shoes",
    "鞋": "shoes",
    "鞋子": "shoes",
    "运动鞋": "shoes",
    "accessory": "accessory",
    "accessories": "accessory",
    "配饰": "accessory",
    "帽子": "accessory",
    "围巾": "accessory",
}

CATEGORY_LABELS = {
    "top": "上衣",
    "bottom": "下装",
    "outer": "外套",
    "shoes": "鞋子",
    "accessory": "配饰",
}

CATEGORY_DEFAULT_NAMES = {
    "top": "自动识别上衣",
    "bottom": "自动识别下装",
    "outer": "自动识别外套",
    "shoes": "自动识别鞋子",
    "accessory": "自动识别配饰",
}

COLOR_RGB = {
    "black": (25, 25, 25),
    "white": (235, 235, 230),
    "gray": (135, 135, 135),
    "navy": (28, 45, 82),
    "blue": (45, 108, 190),
    "red": (190, 48, 55),
    "green": (54, 135, 74),
    "yellow": (224, 185, 58),
    "brown": (123, 78, 45),
    "beige": (190, 168, 125),
    "purple": (125, 75, 160),
}

COLOR_LABELS = {
    "black": "黑色",
    "white": "白色",
    "gray": "灰色",
    "navy": "藏青色",
    "blue": "蓝色",
    "red": "红色",
    "green": "绿色",
    "yellow": "黄色",
    "brown": "棕色",
    "beige": "米色",
    "purple": "紫色",
}

COLOR_FAMILIES = {
    "black": {"black", "黑", "黑色"},
    "white": {"white", "白", "白色", "cream", "米白"},
    "gray": {"gray", "grey", "灰", "灰色", "silver"},
    "navy": {"navy", "深蓝", "藏青", "navy blue"},
    "blue": {"blue", "蓝", "蓝色", "denim", "牛仔"},
    "red": {"red", "红", "红色", "pink", "粉", "粉色"},
    "green": {"green", "绿", "绿色"},
    "yellow": {"yellow", "黄", "黄色"},
    "brown": {"brown", "棕", "棕色", "coffee", "咖啡"},
    "beige": {"beige", "米色", "卡其", "khaki", "tan"},
    "purple": {"purple", "紫", "紫色"},
}

NEUTRAL_COLOR_FAMILIES = {"black", "white", "gray", "navy", "beige", "blue"}
LIGHT_MATERIALS = {"cotton", "linen", "polyester", "速干", "棉", "亚麻", "涤纶"}
WARM_MATERIALS = {"wool", "fleece", "down", "羽绒", "羊毛", "抓绒", "毛呢"}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def split_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).replace("，", ",").replace("、", ",").split(",")
    return [str(item).strip() for item in raw if str(item).strip()]


def normalize_category(value: Any) -> str:
    text = str(value or "").strip().lower()
    return CATEGORY_ALIASES.get(text, text or "top")


def color_family(color: Any) -> str:
    text = str(color or "").strip().lower()
    if not text:
        return "unknown"
    for family, aliases in COLOR_FAMILIES.items():
        if text == family or text in aliases:
            return family
        if any(alias and alias in text for alias in aliases):
            return family
    return text


def nearest_color_name_from_rgb(rgb: Tuple[float, float, float]) -> Tuple[str, str]:
    r, g, b = rgb
    best_name = "gray"
    best_distance = float("inf")
    for name, target in COLOR_RGB.items():
        tr, tg, tb = target
        distance = (r - tr) ** 2 + (g - tg) ** 2 + (b - tb) ** 2
        if distance < best_distance:
            best_name = name
            best_distance = distance
    return best_name, COLOR_LABELS.get(best_name, best_name)


def viewfinder_crop_box(width: int, height: int) -> Tuple[int, int, int, int]:
    x1 = int(width * 0.16)
    x2 = int(width * 0.84)
    y1 = int(height * 0.10)
    y2 = int(height * 0.90)
    return x1, y1, max(x1 + 1, x2), max(y1 + 1, y2)


def cv2_read_image(cv2: Any, np: Any, image_path: Any) -> Any:
    path_text = str(image_path)
    if path_text.isascii():
        image = cv2.imread(path_text)
        if image is not None:
            return image
    try:
        data = np.fromfile(path_text, dtype=np.uint8)
        if data.size:
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None
    return None


def cv2_write_image(cv2: Any, image_path: Any, image: Any, params: Optional[List[int]] = None) -> bool:
    suffix = pathlib.Path(str(image_path)).suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        suffix = ".jpg"
    ok, encoded = cv2.imencode(suffix, image, params or [])
    if not ok:
        return False
    pathlib.Path(str(image_path)).parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(str(image_path))
    return True


def _display_bgr(color: Any) -> Tuple[int, int, int]:
    family = color_family(color)
    rgb = COLOR_RGB.get(family, COLOR_RGB["gray"])
    r, g, b = rgb
    return int(b), int(g), int(r)


def _shade_bgr(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return tuple(max(0, min(255, int(channel * factor))) for channel in color)  # type: ignore[return-value]


def _draw_soft_shadow(cv2: Any, np: Any, canvas: Any, mask: Any, offset: Tuple[int, int] = (16, 18)) -> None:
    shadow = np.zeros(mask.shape, dtype=np.uint8)
    ox, oy = offset
    h, w = mask.shape[:2]
    shadow[oy:h, ox:w] = mask[: h - oy, : w - ox]
    shadow = cv2.GaussianBlur(shadow, (45, 45), 0)
    alpha = (shadow.astype("float32") / 255.0 * 0.22)[:, :, None]
    shadow_color = np.full_like(canvas, (210, 210, 220))
    canvas[:] = (canvas.astype("float32") * (1 - alpha) + shadow_color.astype("float32") * alpha).astype("uint8")


def _rounded_rect(cv2: Any, canvas: Any, p1: Tuple[int, int], p2: Tuple[int, int], radius: int, color: Tuple[int, int, int], thickness: int = -1) -> None:
    x1, y1 = p1
    x2, y2 = p2
    if thickness < 0:
        cv2.rectangle(canvas, (x1 + radius, y1), (x2 - radius, y2), color, thickness)
        cv2.rectangle(canvas, (x1, y1 + radius), (x2, y2 - radius), color, thickness)
        cv2.circle(canvas, (x1 + radius, y1 + radius), radius, color, thickness)
        cv2.circle(canvas, (x2 - radius, y1 + radius), radius, color, thickness)
        cv2.circle(canvas, (x1 + radius, y2 - radius), radius, color, thickness)
        cv2.circle(canvas, (x2 - radius, y2 - radius), radius, color, thickness)
    else:
        cv2.line(canvas, (x1 + radius, y1), (x2 - radius, y1), color, thickness)
        cv2.line(canvas, (x1 + radius, y2), (x2 - radius, y2), color, thickness)
        cv2.line(canvas, (x1, y1 + radius), (x1, y2 - radius), color, thickness)
        cv2.line(canvas, (x2, y1 + radius), (x2, y2 - radius), color, thickness)
        cv2.ellipse(canvas, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness)
        cv2.ellipse(canvas, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness)
        cv2.ellipse(canvas, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness)
        cv2.ellipse(canvas, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness)


def _draw_stylized_item(cv2: Any, np: Any, category: str, color: Tuple[int, int, int], name: str = "") -> Any:
    canvas_h, canvas_w = 840, 720
    canvas = np.full((canvas_h, canvas_w, 3), (248, 248, 251), dtype=np.uint8)
    shape = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    line = (40, 42, 48) if sum(color) > 560 else (235, 236, 240)
    dark = _shade_bgr(color, 0.72)
    light = _shade_bgr(color, 1.12)
    category = normalize_category(category)

    if category == "bottom":
        pts = np.array([[230, 210], [490, 210], [520, 710], [405, 710], [365, 350], [320, 710], [200, 710]], np.int32)
        cv2.fillPoly(shape, [pts], 255)
        _draw_soft_shadow(cv2, np, canvas, shape)
        cv2.fillPoly(canvas, [pts], color)
        _rounded_rect(cv2, canvas, (220, 185), (500, 240), 18, dark)
        cv2.line(canvas, (360, 240), (365, 700), line, 4)
        cv2.line(canvas, (250, 265), (320, 302), light, 5)
        cv2.line(canvas, (470, 265), (405, 302), light, 5)
        _rounded_rect(cv2, canvas, (205, 688), (322, 730), 14, dark)
        _rounded_rect(cv2, canvas, (398, 688), (515, 730), 14, dark)
    elif category == "outer":
        body = np.array([[250, 205], [470, 205], [520, 690], [200, 690]], np.int32)
        left_sleeve = np.array([[250, 225], [160, 335], [115, 560], [205, 580], [260, 355]], np.int32)
        right_sleeve = np.array([[470, 225], [560, 335], [605, 560], [515, 580], [460, 355]], np.int32)
        cv2.fillPoly(shape, [body, left_sleeve, right_sleeve], 255)
        _draw_soft_shadow(cv2, np, canvas, shape)
        cv2.fillPoly(canvas, [left_sleeve, right_sleeve, body], color)
        cv2.ellipse(canvas, (360, 215), (64, 46), 0, 0, 180, (248, 248, 251), -1)
        cv2.line(canvas, (360, 238), (360, 678), line, 5)
        cv2.line(canvas, (285, 250), (360, 340), light, 4)
        cv2.line(canvas, (435, 250), (360, 340), light, 4)
        _rounded_rect(cv2, canvas, (235, 500), (320, 570), 18, dark)
        _rounded_rect(cv2, canvas, (400, 500), (485, 570), 18, dark)
    elif category == "shoes":
        high_top = "boot" in name.lower() or "靴" in name or color_family(name or "") == "black" or color_family(color) == "black"
        if high_top:
            upper = np.array([[160, 445], [230, 315], [390, 300], [450, 430], [585, 500], [555, 585], [205, 585], [135, 545]], np.int32)
            ankle = np.array([[225, 270], [372, 270], [410, 405], [210, 430]], np.int32)
            cv2.fillPoly(shape, [upper, ankle], 255)
            _draw_soft_shadow(cv2, np, canvas, shape, (18, 20))
            cv2.fillPoly(canvas, [ankle, upper], color)
            cv2.line(canvas, (255, 365), (410, 440), line, 5)
            cv2.line(canvas, (275, 395), (425, 465), line, 5)
        else:
            upper = np.array([[135, 465], [255, 365], [445, 390], [610, 500], [570, 580], [175, 580], [118, 535]], np.int32)
            cv2.fillPoly(shape, [upper], 255)
            _draw_soft_shadow(cv2, np, canvas, shape, (18, 20))
            cv2.fillPoly(canvas, [upper], color)
            cv2.line(canvas, (300, 420), (420, 470), line, 5)
            cv2.line(canvas, (270, 450), (395, 505), line, 5)
        _rounded_rect(cv2, canvas, (105, 560), (620, 640), 38, (58, 60, 66), -1)
        _rounded_rect(cv2, canvas, (125, 545), (598, 606), 30, dark, -1)
        cv2.line(canvas, (150, 622), (560, 622), (230, 230, 235), 6)
    else:
        body = np.array([[250, 210], [470, 210], [520, 665], [200, 665]], np.int32)
        left_sleeve = np.array([[250, 230], [132, 335], [180, 460], [260, 392]], np.int32)
        right_sleeve = np.array([[470, 230], [588, 335], [540, 460], [460, 392]], np.int32)
        cv2.fillPoly(shape, [body, left_sleeve, right_sleeve], 255)
        _draw_soft_shadow(cv2, np, canvas, shape)
        cv2.fillPoly(canvas, [left_sleeve, right_sleeve, body], color)
        cv2.ellipse(canvas, (360, 218), (72, 48), 0, 0, 180, (248, 248, 251), -1)
        cv2.line(canvas, (245, 214), (305, 286), light, 5)
        cv2.line(canvas, (475, 214), (415, 286), light, 5)
        if color_family(name) in {"red", "purple"} or "球衣" in name:
            cv2.rectangle(canvas, (285, 365), (435, 410), light, -1)
            cv2.line(canvas, (285, 430), (435, 430), light, 5)

    return canvas


def crop_viewfinder_image(image_path: str, output_dir: pathlib.Path) -> Dict[str, Any]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return {}

    source = pathlib.Path(image_path)
    image = cv2_read_image(cv2, np, source)
    if image is None:
        return {}
    height, width = image.shape[:2]
    x1, y1, x2, y2 = viewfinder_crop_box(width, height)
    crop = image[y1:y2, x1:x2]
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_name = "%s_viewfinder%s" % (source.stem, source.suffix or ".jpg")
    output_path = output_dir / output_name
    cv2_write_image(cv2, output_path, crop, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
    return {
        "image_path": str(output_path),
        "image_url": "/uploads/%s" % output_name,
        "crop_box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
    }


def make_display_image(
    image_path: str,
    output_dir: pathlib.Path,
    category: Any = "",
    color: Any = "",
    name: Any = "",
) -> Dict[str, str]:
    """Create a clean product-card image for wardrobe/recommendation display."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return {}

    source = pathlib.Path(image_path)
    image = cv2_read_image(cv2, np, source)
    if image is None:
        return {}

    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_name = "%s_display.jpg" % source.stem
    output_path = output_dir / output_name

    category_text = normalize_category(category) if category else ""
    if category_text:
        card = _draw_stylized_item(cv2, np, category_text, _display_bgr(color), str(name or ""))
        cv2_write_image(cv2, output_path, card, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
        return {
            "display_image_path": str(output_path),
            "display_image_url": "/uploads/%s" % output_name,
        }

    height, width = image.shape[:2]
    scale = min(1.0, 1100.0 / max(height, width))
    if scale < 1.0:
        image = cv2.resize(image, (int(width * scale), int(height * scale)))
        height, width = image.shape[:2]

    rect = (
        max(1, int(width * 0.04)),
        max(1, int(height * 0.04)),
        max(2, int(width * 0.92)),
        max(2, int(height * 0.92)),
    )
    mask = np.zeros((height, width), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(image, mask, rect, bgd, fgd, 4, cv2.GC_INIT_WITH_RECT)
        alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    except Exception:
        alpha = np.full((height, width), 255, dtype="uint8")

    kernel = np.ones((5, 5), np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel, iterations=2)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, kernel, iterations=1)
    foreground_ratio = float(np.count_nonzero(alpha)) / max(1, alpha.size)
    if foreground_ratio < 0.08 or foreground_ratio > 0.92:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blur, 28, 90)
        alpha = cv2.dilate(edges, kernel, iterations=5)
        alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel, iterations=4)

    contours, _ = cv2.findContours(alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [contour for contour in contours if cv2.contourArea(contour) > max(90, width * height * 0.002)]
    if contours:
        xs, ys, xe, ye = [], [], [], []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            xs.append(x)
            ys.append(y)
            xe.append(x + w)
            ye.append(y + h)
        x1, y1, x2, y2 = min(xs), min(ys), max(xe), max(ye)
    else:
        x1, y1, x2, y2 = 0, 0, width, height

    pad_x = int((x2 - x1) * 0.08)
    pad_y = int((y2 - y1) * 0.08)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(width, x2 + pad_x)
    y2 = min(height, y2 + pad_y)
    if x2 <= x1 or y2 <= y1:
        x1, y1, x2, y2 = 0, 0, width, height

    crop = image[y1:y2, x1:x2]
    crop_alpha = alpha[y1:y2, x1:x2]
    canvas_h, canvas_w = 840, 720
    canvas = np.full((canvas_h, canvas_w, 3), (247, 247, 250), dtype=np.uint8)
    shadow = np.zeros((canvas_h, canvas_w), dtype=np.uint8)

    ch, cw = crop.shape[:2]
    fit = min(canvas_w * 0.82 / max(1, cw), canvas_h * 0.78 / max(1, ch))
    nw, nh = max(1, int(cw * fit)), max(1, int(ch * fit))
    crop = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
    crop_alpha = cv2.resize(crop_alpha, (nw, nh), interpolation=cv2.INTER_AREA)
    crop_alpha = cv2.GaussianBlur(crop_alpha, (5, 5), 0)
    ox = (canvas_w - nw) // 2
    oy = (canvas_h - nh) // 2

    shadow_y = min(canvas_h - nh, oy + 14)
    shadow_x = min(canvas_w - nw, ox + 10)
    shadow[shadow_y : shadow_y + nh, shadow_x : shadow_x + nw] = crop_alpha
    shadow = cv2.GaussianBlur(shadow, (31, 31), 0)
    shadow_layer = np.full_like(canvas, (210, 210, 220))
    shadow_alpha = (shadow.astype("float32") / 255.0 * 0.28)[:, :, None]
    canvas = (canvas.astype("float32") * (1 - shadow_alpha) + shadow_layer.astype("float32") * shadow_alpha).astype("uint8")

    roi = canvas[oy : oy + nh, ox : ox + nw]
    alpha_f = (crop_alpha.astype("float32") / 255.0)[:, :, None]
    blended = crop.astype("float32") * alpha_f + roi.astype("float32") * (1 - alpha_f)
    canvas[oy : oy + nh, ox : ox + nw] = blended.astype("uint8")

    cv2_write_image(cv2, output_path, canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    return {
        "display_image_path": str(output_path),
        "display_image_url": "/uploads/%s" % output_name,
    }


class CloudPreprocessor:
    """Optional cloud subject extraction before edge-side recognition."""

    def __init__(self, upload_dir: pathlib.Path):
        self.upload_dir = pathlib.Path(upload_dir)
        self.provider = os.environ.get("SMART_WARDROBE_CLOUD_PROVIDER", "gemini").strip().lower()
        self.model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
        self.proxy_url = os.environ.get("SMART_WARDROBE_CLOUD_PROXY_URL", "").strip()
        self.api_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("SMART_WARDROBE_GEMINI_API_KEY")
            or ""
        ).strip()
        self.timeout = float(os.environ.get("SMART_WARDROBE_CLOUD_TIMEOUT", "4.2") or 4.2)

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "configured": self.configured(),
            "proxy_url": self.proxy_url,
            "timeout_sec": self.timeout,
            "purpose": "subject_bbox_crop",
        }

    def configured(self) -> bool:
        return self.provider == "gemini" and (bool(self.api_key) or bool(self.proxy_url))

    def preprocess(self, image_path: str, image_url: str = "") -> Dict[str, Any]:
        started = time.perf_counter()
        if not self.configured():
            return {
                "ok": False,
                "used": False,
                "provider": self.provider,
                "reason": "missing_api_key",
                "message": "Set GEMINI_API_KEY to enable cloud subject extraction.",
            }
        try:
            if self.proxy_url:
                result = self._preprocess_with_proxy(pathlib.Path(image_path), image_url)
            else:
                result = self._preprocess_with_gemini(pathlib.Path(image_path), image_url)
            result["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
            return result
        except Exception as exc:
            return {
                "ok": False,
                "used": False,
                "provider": self.provider,
                "model": self.model,
                "reason": "cloud_error",
                "message": str(exc)[:500],
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
            }

    def _preprocess_with_proxy(self, image_path: pathlib.Path, image_url: str) -> Dict[str, Any]:
        if not image_path.exists():
            raise FileNotFoundError(str(image_path))
        mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        body = {
            "mime_type": mime_type,
            "image_data": base64.b64encode(image_path.read_bytes()).decode("ascii"),
            "model": self.model,
            "timeout_sec": self.timeout,
        }
        request = urllib.request.Request(
            self.proxy_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._urlopen_ipv4(request, timeout=self.timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            raise RuntimeError(str(result.get("message") or result.get("reason") or "cloud proxy failed"))
        box = self._normalized_box(result.get("normalized_box") or result.get("box_2d"))
        crop = self._crop_to_box(image_path, box)
        crop.update(
            {
                "ok": True,
                "used": True,
                "provider": str(result.get("provider") or "gemini_proxy"),
                "model": str(result.get("model") or self.model),
                "source_image_path": str(image_path),
                "source_image_url": image_url,
                "label": str(result.get("label") or "garment"),
                "confidence": float(result.get("confidence") or 0),
                "quality": str(result.get("quality") or "ok"),
                "reason": str(result.get("reason") or "")[:240],
                "normalized_box": box,
                "via_proxy": True,
            }
        )
        return crop

    def _preprocess_with_gemini(self, image_path: pathlib.Path, image_url: str) -> Dict[str, Any]:
        if not image_path.exists():
            raise FileNotFoundError(str(image_path))
        image_bytes = image_path.read_bytes()
        mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
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
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
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
            + urllib.parse.quote(self.model, safe="-_.")
            + ":generateContent?key="
            + urllib.parse.quote(self.api_key)
        )
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._urlopen_ipv4(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = self._gemini_text(payload)
        result = self._parse_json_object(text)
        box = self._normalized_box(result.get("box_2d"))
        crop = self._crop_to_box(image_path, box)
        crop.update(
            {
                "ok": True,
                "used": True,
                "provider": "gemini",
                "model": self.model,
                "source_image_path": str(image_path),
                "source_image_url": image_url,
                "label": str(result.get("label") or "garment"),
                "confidence": float(result.get("confidence") or 0),
                "quality": str(result.get("quality") or "ok"),
                "reason": str(result.get("reason") or "")[:240],
                "normalized_box": box,
            }
        )
        return crop

    def _urlopen_ipv4(self, request: urllib.request.Request, timeout: float) -> Any:
        original_getaddrinfo = socket.getaddrinfo

        def getaddrinfo_ipv4(*args: Any, **kwargs: Any) -> Any:
            infos = original_getaddrinfo(*args, **kwargs)
            ipv4_infos = [info for info in infos if info[0] == socket.AF_INET]
            return ipv4_infos or infos

        socket.getaddrinfo = getaddrinfo_ipv4  # type: ignore[assignment]
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        finally:
            socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]

    def _gemini_text(self, payload: Dict[str, Any]) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        text = "\n".join(str(part.get("text") or "") for part in parts if part.get("text"))
        if not text.strip():
            raise RuntimeError("Gemini returned empty text")
        return text

    def _parse_json_object(self, text: str) -> Dict[str, Any]:
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

    def _normalized_box(self, value: Any) -> List[int]:
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

    def _crop_to_box(self, image_path: pathlib.Path, normalized_box: List[int]) -> Dict[str, Any]:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception as exc:
            raise RuntimeError("OpenCV unavailable for cloud crop: %s" % exc) from exc
        image = cv2_read_image(cv2, np, image_path)
        if image is None:
            raise RuntimeError("cannot read image for cloud crop: %s" % image_path)
        height, width = image.shape[:2]
        y1n, x1n, y2n, x2n = normalized_box
        x1 = int(width * x1n / 1000)
        x2 = int(width * x2n / 1000)
        y1 = int(height * y1n / 1000)
        y2 = int(height * y2n / 1000)
        pad_x = max(6, int((x2 - x1) * 0.08))
        pad_y = max(6, int((y2 - y1) * 0.08))
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(width, x2 + pad_x)
        y2 = min(height, y2 + pad_y)
        if x2 <= x1 or y2 <= y1:
            x1, y1, x2, y2 = 0, 0, width, height
        crop = image[y1:y2, x1:x2]
        output_name = "%s_cloud%s" % (image_path.stem, image_path.suffix or ".jpg")
        output_path = self.upload_dir / output_name
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        cv2_write_image(cv2, output_path, crop, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
        return {
            "image_path": str(output_path),
            "image_url": "/uploads/%s" % output_name,
            "crop_box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        }


def season_for_temperature(temp_c: float) -> str:
    if temp_c < 10:
        return "winter"
    if temp_c < 20:
        return "spring_autumn"
    if temp_c < 28:
        return "summer_light"
    return "summer_hot"


def target_warmth(temp_c: float) -> int:
    if temp_c <= 5:
        return 5
    if temp_c <= 12:
        return 4
    if temp_c <= 20:
        return 3
    if temp_c <= 27:
        return 2
    return 1


def weather_code_text(code: Optional[int]) -> str:
    if code is None:
        return "未知"
    if code == 0:
        return "晴"
    if code in {1, 2, 3}:
        return "多云"
    if code in {45, 48}:
        return "雾"
    if 51 <= code <= 67:
        return "小雨"
    if 71 <= code <= 77:
        return "雪"
    if 80 <= code <= 82:
        return "阵雨"
    if code in {95, 96, 99}:
        return "雷雨"
    return "天气码 %s" % code


class WardrobeDB:
    def __init__(self, db_path: pathlib.Path):
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clothes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    color TEXT DEFAULT '',
                    material TEXT DEFAULT '',
                    season TEXT DEFAULT '',
                    occasion TEXT DEFAULT '',
                    style TEXT DEFAULT '',
                    warmth INTEGER DEFAULT 3,
                    formality INTEGER DEFAULT 2,
                    favorite_score INTEGER DEFAULT 3,
                    category_confidence REAL DEFAULT 0,
                    color_confidence REAL DEFAULT 0,
                    material_confidence REAL DEFAULT 0,
                    wear_count INTEGER DEFAULT 0,
                    image_url TEXT DEFAULT '',
                    image_path TEXT DEFAULT '',
                    display_image_url TEXT DEFAULT '',
                    display_image_path TEXT DEFAULT '',
                    ai_analysis TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_worn_at TEXT DEFAULT ''
                )
                """
            )
            self._ensure_columns(conn)
            conn.commit()

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(clothes)").fetchall()
        existing = {row["name"] for row in rows}
        columns = {
            "category_confidence": "REAL DEFAULT 0",
            "color_confidence": "REAL DEFAULT 0",
            "material_confidence": "REAL DEFAULT 0",
            "ai_analysis": "TEXT DEFAULT ''",
            "display_image_url": "TEXT DEFAULT ''",
            "display_image_path": "TEXT DEFAULT ''",
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute("ALTER TABLE clothes ADD COLUMN %s %s" % (name, definition))

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        item = dict(row)
        item["season_tags"] = split_tags(item.get("season"))
        item["occasion_tags"] = split_tags(item.get("occasion"))
        item["category_label"] = CATEGORY_LABELS.get(item["category"], item["category"])
        item["color_family"] = color_family(item.get("color"))
        try:
            item["ai_analysis"] = json.loads(item.get("ai_analysis") or "{}")
        except json.JSONDecodeError:
            item["ai_analysis"] = {}
        return item

    def list_clothes(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM clothes ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_clothing(self, item_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM clothes WHERE id=?", (item_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def add_clothing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        created = now_iso()
        item = self._clean_payload(payload)
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO clothes (
                    name, category, color, material, season, occasion, style,
                    warmth, formality, favorite_score, category_confidence,
                    color_confidence, material_confidence, wear_count, image_url,
                    image_path, display_image_url, display_image_path, ai_analysis,
                    note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["name"],
                    item["category"],
                    item["color"],
                    item["material"],
                    item["season"],
                    item["occasion"],
                    item["style"],
                    item["warmth"],
                    item["formality"],
                    item["favorite_score"],
                    item["category_confidence"],
                    item["color_confidence"],
                    item["material_confidence"],
                    0,
                    item["image_url"],
                    item["image_path"],
                    item["display_image_url"],
                    item["display_image_path"],
                    item["ai_analysis"],
                    item["note"],
                    created,
                    created,
                ),
            )
            conn.commit()
            item_id = int(cur.lastrowid)
        added = self.get_clothing(item_id)
        assert added is not None
        return added

    def update_clothing(self, item_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.get_clothing(item_id)
        if not existing:
            return None
        merged = dict(existing)
        merged.update(payload)
        cleaned = self._clean_payload(merged)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE clothes SET
                    name=?, category=?, color=?, material=?, season=?,
                    occasion=?, style=?, warmth=?, formality=?,
                    favorite_score=?, category_confidence=?, color_confidence=?,
                    material_confidence=?, image_url=?, image_path=?,
                    display_image_url=?, display_image_path=?, ai_analysis=?,
                    note=?, updated_at=?
                WHERE id=?
                """,
                (
                    cleaned["name"],
                    cleaned["category"],
                    cleaned["color"],
                    cleaned["material"],
                    cleaned["season"],
                    cleaned["occasion"],
                    cleaned["style"],
                    cleaned["warmth"],
                    cleaned["formality"],
                    cleaned["favorite_score"],
                    cleaned["category_confidence"],
                    cleaned["color_confidence"],
                    cleaned["material_confidence"],
                    cleaned["image_url"],
                    cleaned["image_path"],
                    cleaned["display_image_url"],
                    cleaned["display_image_path"],
                    cleaned["ai_analysis"],
                    cleaned["note"],
                    now_iso(),
                    item_id,
                ),
            )
            conn.commit()
        return self.get_clothing(item_id)

    def delete_clothing(self, item_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM clothes WHERE id=?", (item_id,))
            conn.commit()
            return cur.rowcount > 0

    def count(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM clothes").fetchone()
        return int(row["n"])

    def seed_demo_items(self, force: bool = False) -> int:
        if self.count() and not force:
            return 0
        demo_items = [
            {
                "name": "演示白色卫衣",
                "category": "top",
                "color": "white",
                "material": "cotton",
                "season": "spring_autumn,winter",
                "occasion": "school,commute,casual",
                "warmth": 3,
                "formality": 2,
                "favorite_score": 4,
                "note": "演示数据，可删除后录入真实衣物",
            },
            {
                "name": "演示深色长裤",
                "category": "bottom",
                "color": "black",
                "material": "cotton",
                "season": "spring_autumn,winter,summer_light",
                "occasion": "school,commute,casual",
                "warmth": 3,
                "formality": 3,
                "favorite_score": 4,
                "note": "演示数据，可删除后录入真实衣物",
            },
            {
                "name": "演示薄外套",
                "category": "outer",
                "color": "navy",
                "material": "polyester",
                "season": "spring_autumn",
                "occasion": "school,commute,casual",
                "warmth": 3,
                "formality": 2,
                "favorite_score": 3,
                "note": "演示数据，可删除后录入真实衣物",
            },
            {
                "name": "演示运动鞋",
                "category": "shoes",
                "color": "white",
                "material": "polyester",
                "season": "spring_autumn,winter,summer_light,summer_hot",
                "occasion": "school,commute,sport,casual",
                "warmth": 2,
                "formality": 1,
                "favorite_score": 4,
                "note": "演示数据，可删除后录入真实衣物",
            },
        ]
        for item in demo_items:
            self.add_clothing(item)
        return len(demo_items)

    def _clean_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = str(payload.get("name") or "未命名衣物").strip()[:80]
        season = ",".join(split_tags(payload.get("season")))
        occasion = ",".join(split_tags(payload.get("occasion")))
        return {
            "name": name or "未命名衣物",
            "category": normalize_category(payload.get("category")),
            "color": str(payload.get("color") or "").strip()[:40],
            "material": str(payload.get("material") or "").strip()[:60],
            "season": season,
            "occasion": occasion,
            "style": str(payload.get("style") or "").strip()[:60],
            "warmth": clamp_int(payload.get("warmth"), 3, 1, 5),
            "formality": clamp_int(payload.get("formality"), 2, 1, 5),
            "favorite_score": clamp_int(payload.get("favorite_score"), 3, 1, 5),
            "category_confidence": float(payload.get("category_confidence") or 0),
            "color_confidence": float(payload.get("color_confidence") or 0),
            "material_confidence": float(payload.get("material_confidence") or 0),
            "image_url": str(payload.get("image_url") or "").strip()[:240],
            "image_path": str(payload.get("image_path") or "").strip()[:240],
            "display_image_url": str(payload.get("display_image_url") or "").strip()[:240],
            "display_image_path": str(payload.get("display_image_path") or "").strip()[:240],
            "ai_analysis": self._normalize_analysis(payload.get("ai_analysis")),
            "note": str(payload.get("note") or "").strip()[:240],
        }

    def _normalize_analysis(self, value: Any) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            try:
                json.loads(value)
                return value[:4000]
            except json.JSONDecodeError:
                return json.dumps({"raw": value}, ensure_ascii=False)
        return json.dumps(value, ensure_ascii=False)[:4000]


class ImageAnalyzer:
    """Lightweight image analysis for clothing ingestion.

    This is a rule-based MVP. Color is usually useful; material and category are
    approximate guesses because they depend on camera angle, background and how
    the clothing is placed.
    """

    def __init__(self, model_path: Optional[pathlib.Path] = None):
        self.model_path = pathlib.Path(
            model_path
            or os.environ.get(
                "SMART_WARDROBE_VISION_MODEL",
                "/root/workspace/smart-wardrobe/data/vision_model.json",
            )
        )
        self._model_mtime = 0.0
        self._model_cache: Dict[str, Any] = {}

    def analyze(self, image_path: str, focus_viewfinder: bool = False) -> Dict[str, Any]:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception as exc:
            return self._fallback("opencv_missing", str(exc))

        image = cv2_read_image(cv2, np, image_path)
        if image is None:
            return self._fallback("image_read_failed", str(image_path))

        height, width = image.shape[:2]
        scale = 640.0 / max(height, width)
        if scale < 1.0:
            image = cv2.resize(image, (int(width * scale), int(height * scale)))
            height, width = image.shape[:2]
        if focus_viewfinder:
            image = self._crop_viewfinder(image)
            height, width = image.shape[:2]

        corrected, lighting = self._normalize_lighting(cv2, np, image)
        mask, bbox = self._object_mask(cv2, np, corrected)
        color_result = self._dominant_color(cv2, np, image, corrected, mask, lighting)
        material_result = self._material_hint(cv2, np, corrected, mask, color_result["family"])
        category_result = self._category_hint(width, height, bbox, material_result["material"])
        model_match = self._match_demo_model(cv2, np, image)
        matched_label = model_match["label"] if model_match else {}
        if model_match:
            label = matched_label
            category_result = dict(category_result)
            category_result["category"] = normalize_category(label.get("category"))
            category_result["confidence"] = max(float(category_result["confidence"]), 0.98)
            color_name = str(label.get("color") or "").strip()
            color_result = dict(color_result)
            color_result["family"] = color_family(color_name)
            color_result["label"] = str(label.get("color_label") or COLOR_LABELS.get(color_name, color_name))
            color_result["confidence"] = max(float(color_result["confidence"]), 0.98)
            material_result = dict(material_result)
            material_result["material"] = str(label.get("material") or material_result["material"])
            material_result["label"] = str(label.get("material_label") or material_result["label"])
            material_result["confidence"] = max(float(material_result["confidence"]), 0.96)

        confidence = {
            "category": category_result["confidence"],
            "color": color_result["confidence"],
            "material": material_result["confidence"],
        }
        return {
            "ok": True,
            "item_id": matched_label.get("id"),
            "item_name": matched_label.get("name"),
            "category": category_result["category"],
            "category_label": matched_label.get("category_label")
            or CATEGORY_LABELS.get(category_result["category"], category_result["category"]),
            "color": color_result["label"],
            "color_family": color_result["family"],
            "material": material_result["material"],
            "material_label": material_result["label"],
            "confidence": confidence,
            "bbox": bbox,
            "features": {
                "dominant_rgb": color_result["rgb"],
                "laplacian_var": material_result["laplacian_var"],
                "saturation_mean": material_result["saturation_mean"],
                "highlight_ratio": material_result["highlight_ratio"],
                "object_area_ratio": category_result["area_ratio"],
                "object_aspect": category_result["aspect"],
                "mask_source": category_result.get("mask_source", ""),
                "score_margin": category_result.get("score_margin", 0),
                "model_match": model_match.get("summary") if model_match else None,
                "brightness_mean": lighting["brightness_mean"],
                "low_light": lighting["low_light"],
            },
            "warnings": self._warnings(lighting) + [
                "类别和材质为规则推测，拍摄角度、背景、折叠方式会影响结果。",
                "材质识别只能作为入库初值，比赛展示时建议允许人工修正。",
            ],
            "reason": self._analysis_reason(color_result, material_result, category_result),
        }

    def _load_demo_model(self) -> Dict[str, Any]:
        try:
            if not self.model_path.exists():
                return {}
            mtime = self.model_path.stat().st_mtime
            if self._model_cache and mtime == self._model_mtime:
                return self._model_cache
            self._model_cache = json.loads(self.model_path.read_text(encoding="utf-8"))
            self._model_mtime = mtime
            return self._model_cache
        except Exception:
            return {}

    def _match_demo_model(self, cv2: Any, np: Any, image: Any) -> Optional[Dict[str, Any]]:
        model = self._load_demo_model()
        labels = model.get("labels") or []
        if not labels:
            return None
        vector = self._feature_vector(cv2, np, image)
        best: Optional[Tuple[float, Dict[str, Any]]] = None
        for label in labels:
            references = []
            if label.get("prototype"):
                references.append(label.get("prototype") or [])
            references.extend(label.get("sample_vectors") or [])
            for reference in references:
                if len(reference) != len(vector):
                    continue
                distance = sum((float(a) - float(b)) ** 2 for a, b in zip(vector, reference)) ** 0.5
                if best is None or distance < best[0]:
                    best = (distance, label)
        if not best:
            return None
        distance, label = best
        threshold = float(label.get("threshold") or model.get("threshold") or 0.42)
        if distance > threshold:
            return None
        score = max(0.0, min(1.0, 1.0 - distance / max(threshold, 1e-6)))
        return {
            "label": label,
            "summary": {
                "id": label.get("id"),
                "name": label.get("name"),
                "distance": round(distance, 4),
                "threshold": round(threshold, 4),
                "score": round(score, 3),
            },
        }

    def _feature_vector(self, cv2: Any, np: Any, image: Any) -> List[float]:
        small = cv2.resize(image, (96, 96))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype("float32") / 255.0
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        pixels = rgb.reshape((-1, 3))
        mean = pixels.mean(axis=0).tolist()
        std = pixels.std(axis=0).tolist()
        h = hsv[:, :, 0].reshape(-1)
        s = hsv[:, :, 1].reshape(-1)
        v = hsv[:, :, 2].reshape(-1)
        valid = (s > 24) & (v > 24)
        if valid.any():
            hist = np.histogram(h[valid], bins=8, range=(0, 180))[0].astype("float32")
        else:
            hist = np.zeros(8, dtype="float32")
        hist = hist / max(1.0, float(hist.sum()))
        return [float(x) for x in mean + std + hist.tolist()]

    def _crop_viewfinder(self, image: Any) -> Any:
        height, width = image.shape[:2]
        x1 = int(width * 0.16)
        x2 = int(width * 0.84)
        y1 = int(height * 0.10)
        y2 = int(height * 0.90)
        if x2 <= x1 or y2 <= y1:
            return image
        return image[y1:y2, x1:x2]

    def _fallback(self, reason: str, detail: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "category": "top",
            "category_label": CATEGORY_LABELS["top"],
            "color": "",
            "color_family": "unknown",
            "material": "cotton",
            "material_label": "棉/未知",
            "confidence": {"category": 0.1, "color": 0.0, "material": 0.1},
            "features": {},
            "warnings": ["图像分析不可用：%s" % reason],
            "reason": [detail],
        }

    def _normalize_lighting(self, cv2: Any, np: Any, image: Any) -> Tuple[Any, Dict[str, Any]]:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        brightness = float(hsv[:, :, 2].mean())
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l2 = clahe.apply(l)
        corrected = cv2.cvtColor(cv2.merge((l2, a, b)), cv2.COLOR_LAB2BGR)
        if brightness < 70:
            gamma = 0.72
            table = np.array([((i / 255.0) ** gamma) * 255 for i in range(256)]).astype("uint8")
            corrected = cv2.LUT(corrected, table)
        return corrected, {
            "brightness_mean": round(brightness, 2),
            "low_light": brightness < 70,
        }

    def _object_mask(self, cv2: Any, np: Any, image: Any) -> Tuple[Any, Dict[str, int]]:
        height, width = image.shape[:2]
        category_bbox: Optional[Dict[str, Any]] = None
        try:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype("float32")
            strip = max(8, min(width, height) // 18)
            border = np.concatenate(
                [
                    lab[:strip, :, :].reshape(-1, 3),
                    lab[-strip:, :, :].reshape(-1, 3),
                    lab[:, :strip, :].reshape(-1, 3),
                    lab[:, -strip:, :].reshape(-1, 3),
                ],
                axis=0,
            )
            bg = np.median(border, axis=0)
            dist = np.linalg.norm(lab - bg, axis=2)
            threshold = max(18.0, float(np.percentile(dist, 72)))
            mask = np.where(dist > threshold, 255, 0).astype("uint8")
            central = np.zeros_like(mask)
            central[int(height * 0.05) : int(height * 0.95), int(width * 0.05) : int(width * 0.95)] = 255
            mask = cv2.bitwise_and(mask, central)
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                contour = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(contour)
                area_ratio = (w * h) / max(1, width * height)
                if 0.035 <= area_ratio <= 0.88:
                    category_bbox = {
                        "x": int(x),
                        "y": int(y),
                        "w": int(w),
                        "h": int(h),
                        "source": "border_delta",
                    }
        except Exception:
            pass

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        # Remove very bright, low-saturation background. Keep dark and colored clothing.
        mask = np.where((v > 245) & (s < 24), 0, 255).astype("uint8")
        # Give the central area more chance when the background is complex.
        central = np.zeros_like(mask)
        x1, x2 = int(width * 0.08), int(width * 0.92)
        y1, y2 = int(height * 0.08), int(height * 0.92)
        central[y1:y2, x1:x2] = 255
        mask = cv2.bitwise_and(mask, central)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            fallback = {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1, "source": "center_fallback"}
            return mask, category_bbox or fallback
        contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(contour)
        if w * h < width * height * 0.04:
            fallback = {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1, "source": "center_fallback"}
            return mask, category_bbox or fallback
        refined = np.zeros_like(mask)
        cv2.drawContours(refined, [contour], -1, 255, thickness=-1)
        threshold_bbox = {"x": int(x), "y": int(y), "w": int(w), "h": int(h), "source": "threshold"}
        return refined, category_bbox or threshold_bbox

    def _dominant_color(
        self, cv2: Any, np: Any, original: Any, corrected: Any, mask: Any, lighting: Dict[str, Any]
    ) -> Dict[str, Any]:
        pixels = corrected[mask > 0]
        original_pixels = original[mask > 0]
        if len(pixels) < 200:
            h, w = corrected.shape[:2]
            crop = corrected[int(h * 0.2) : int(h * 0.8), int(w * 0.2) : int(w * 0.8)]
            pixels = crop.reshape((-1, 3))
            original_pixels = original[int(h * 0.2) : int(h * 0.8), int(w * 0.2) : int(w * 0.8)].reshape((-1, 3))
        original_hsv = cv2.cvtColor(original_pixels.reshape((-1, 1, 3)), cv2.COLOR_BGR2HSV).reshape((-1, 3))
        hsv_pixels = cv2.cvtColor(pixels.reshape((-1, 1, 3)), cv2.COLOR_BGR2HSV).reshape((-1, 3))
        # Ignore tiny pure-white specular/background pixels when enough colored pixels exist.
        s = hsv_pixels[:, 1]
        v = hsv_pixels[:, 2]
        useful = pixels[~((v > 245) & (s < 18))]
        if len(useful) > 200:
            pixels = useful
        median_bgr = np.median(pixels, axis=0)
        original_v_median = float(np.median(original_hsv[:, 2]))
        original_s_median = float(np.median(original_hsv[:, 1]))
        if original_v_median < 42 and original_s_median < 90:
            median_bgr = np.array([25, 25, 25])
        b, g, r = [float(x) for x in median_bgr]
        family, label = nearest_color_name_from_rgb((r, g, b))
        spread = float(np.mean(np.std(pixels, axis=0)))
        confidence = max(0.35, min(0.88, 0.88 - spread / 160.0))
        if lighting.get("low_light"):
            confidence = min(confidence, 0.66)
        return {
            "family": family,
            "label": label,
            "rgb": [round(r, 1), round(g, 1), round(b, 1)],
            "confidence": round(confidence, 2),
        }

    def _material_hint(
        self, cv2: Any, np: Any, image: Any, mask: Any, color_name: str
    ) -> Dict[str, Any]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        selected_gray = gray[mask > 0]
        selected_hsv = hsv[mask > 0]
        if len(selected_gray) < 200:
            selected_gray = gray.reshape(-1)
            selected_hsv = hsv.reshape((-1, 3))
        laplacian_var = float(cv2.Laplacian(selected_gray, cv2.CV_64F).var())
        saturation_mean = float(selected_hsv[:, 1].mean())
        value = selected_hsv[:, 2]
        saturation = selected_hsv[:, 1]
        highlight_ratio = float(((value > 225) & (saturation < 75)).mean())

        material = "cotton"
        label = "棉/棉混纺"
        confidence = 0.36
        if color_name in {"blue", "navy"} and laplacian_var > 850:
            material, label, confidence = "denim", "牛仔/斜纹织物", 0.48
        elif color_name in {"black", "brown"} and highlight_ratio > 0.18:
            material, label, confidence = "leather", "皮革/亮面材质", 0.42
        elif laplacian_var > 1500 and saturation_mean < 95:
            material, label, confidence = "wool", "毛织/粗纹理", 0.43
        elif highlight_ratio > 0.22:
            material, label, confidence = "polyester", "涤纶/亮面化纤", 0.4
        elif laplacian_var < 220:
            material, label, confidence = "cotton", "棉/平纹织物", 0.38
        return {
            "material": material,
            "label": label,
            "confidence": confidence,
            "laplacian_var": round(laplacian_var, 2),
            "saturation_mean": round(saturation_mean, 2),
            "highlight_ratio": round(highlight_ratio, 3),
        }

    def _category_hint(
        self, width: int, height: int, bbox: Dict[str, int], material: str
    ) -> Dict[str, Any]:
        aspect = bbox["w"] / max(1, bbox["h"])
        area_ratio = (bbox["w"] * bbox["h"]) / max(1, width * height)
        rel_h = bbox["h"] / max(1, height)
        rel_w = bbox["w"] / max(1, width)
        center_y = (bbox["y"] + bbox["h"] / 2) / max(1, height)
        scores = {
            "top": 0.24,
            "bottom": 0.22,
            "outer": 0.18,
            "shoes": 0.18,
        }

        if aspect > 1.65:
            scores["shoes"] += 0.24
        if aspect > 2.15 and rel_h < 0.5:
            scores["shoes"] += 0.18
        if rel_h < 0.48 and center_y > 0.48:
            scores["shoes"] += 0.14
        if rel_w > 0.7 and rel_h < 0.55:
            scores["shoes"] += 0.08

        if aspect < 0.72 and rel_h > 0.52:
            scores["bottom"] += 0.24
        if aspect < 0.9 and rel_h > 0.62:
            scores["bottom"] += 0.12
        if center_y > 0.46 and rel_h > 0.55:
            scores["bottom"] += 0.08

        if 0.72 <= aspect <= 1.65 and area_ratio > 0.28:
            scores["top"] += 0.16
        if 0.82 <= aspect <= 1.45 and 0.35 <= rel_h <= 0.78:
            scores["top"] += 0.14
        if center_y < 0.58 and rel_w > 0.34:
            scores["top"] += 0.08

        if material in {"wool", "leather", "fleece", "down"}:
            scores["outer"] += 0.16
        if area_ratio > 0.5 and rel_h > 0.62:
            scores["outer"] += 0.1

        ordered = sorted(scores.items(), key=lambda entry: entry[1], reverse=True)
        category, best_score = ordered[0]
        second_score = ordered[1][1]
        margin = best_score - second_score
        confidence = min(0.88, max(0.32, best_score + margin * 0.45))
        if bbox.get("source") == "border_delta":
            confidence = min(0.9, confidence + 0.04)
        elif bbox.get("source") == "center_fallback":
            confidence = min(confidence, 0.36)
        if margin < 0.05:
            confidence = min(confidence, 0.48)
        return {
            "category": category,
            "confidence": round(confidence, 3),
            "aspect": round(aspect, 3),
            "area_ratio": round(area_ratio, 3),
            "mask_source": bbox.get("source", ""),
            "score_margin": round(margin, 3),
            "scores": {key: round(value, 3) for key, value in scores.items()},
        }

    def _analysis_reason(
        self, color_result: Dict[str, Any], material_result: Dict[str, Any], category_result: Dict[str, Any]
    ) -> List[str]:
        return [
            "颜色按主体区域 RGB 中值匹配到 %s" % color_result["label"],
            "材质根据纹理清晰度、饱和度和高光比例推测为 %s" % material_result["label"],
            "类别根据主体外接框比例推测为 %s" % CATEGORY_LABELS.get(category_result["category"], category_result["category"]),
        ]

    def _warnings(self, lighting: Dict[str, Any]) -> List[str]:
        if lighting.get("low_light"):
            return ["当前画面偏暗，颜色识别置信度已降低，建议补光或靠近衣物。"]
        return []


def merge_analysis_into_payload(payload: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(payload)
    category_value = str(merged.get("category") or "").strip().lower()
    if not category_value or category_value == "auto":
        merged["category"] = analysis.get("category", "top")
    if not str(merged.get("name") or "").strip():
        merged["name"] = analysis.get("item_name") or CATEGORY_DEFAULT_NAMES.get(
            merged.get("category"), "自动识别衣物"
        )
    if not str(merged.get("color") or "").strip():
        merged["color"] = analysis.get("color", "")
    if not str(merged.get("material") or "").strip():
        merged["material"] = analysis.get("material", "cotton")
    if not merged.get("warmth"):
        merged["warmth"] = _warmth_from_material(str(merged.get("material") or "cotton"))
    confidence = analysis.get("confidence") or {}
    merged["category_confidence"] = confidence.get("category", 0)
    merged["color_confidence"] = confidence.get("color", 0)
    merged["material_confidence"] = confidence.get("material", 0)
    merged["ai_analysis"] = analysis
    note = str(merged.get("note") or "").strip()
    reason = "；".join(analysis.get("reason") or [])
    merged["note"] = (note + " " + reason).strip()[:240]
    return merged


def _warmth_from_material(material: str) -> int:
    text = material.lower()
    if text in {"wool", "fleece", "down", "leather"}:
        return 4
    if text in {"linen", "polyester"}:
        return 2
    return 3


class Camera:
    def __init__(self, upload_dir: pathlib.Path, device: str = "/dev/video0"):
        self.upload_dir = pathlib.Path(upload_dir)
        self.device = device
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._latest_jpeg: Optional[bytes] = None
        self._latest_ts = 0.0
        self._stream_error = ""

    def available(self) -> bool:
        return pathlib.Path(self.device).exists()

    def start_live(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._live_loop, name="camera-live", daemon=True)
        self._thread.start()

    def _live_loop(self) -> None:
        try:
            import cv2  # type: ignore
        except Exception as exc:
            self._stream_error = "OpenCV unavailable: %s" % exc
            return

        while not self._stop_event.is_set():
            if not self.available():
                self._stream_error = "%s does not exist" % self.device
                time.sleep(1.0)
                continue
            cap = cv2.VideoCapture(self.device)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 15)
            if not cap.isOpened():
                self._stream_error = "cannot open %s" % self.device
                time.sleep(1.0)
                continue
            self._stream_error = ""
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    self._stream_error = "camera read failed"
                    break
                ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if ok:
                    with self._lock:
                        self._latest_jpeg = encoded.tobytes()
                        self._latest_ts = time.time()
                time.sleep(0.06)
            cap.release()
            time.sleep(0.3)

    def capture(self, resolution: str = "640x480", skip_frames: int = 10) -> Dict[str, str]:
        if not self.available():
            raise RuntimeError("%s does not exist" % self.device)
        latest = self.latest_jpeg(max_age=2.5)
        if latest:
            filename = "clothes_%s.jpg" % datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.upload_dir / filename
            output_path.write_bytes(latest)
            return {
                "image_path": str(output_path),
                "image_url": "/uploads/%s" % filename,
                "log": "Captured from live camera buffer.",
            }
        if not shutil.which("fswebcam"):
            raise RuntimeError("fswebcam is not installed")
        filename = "clothes_%s.jpg" % datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.upload_dir / filename
        cmd = [
            "fswebcam",
            "-d",
            self.device,
            "-r",
            resolution,
            "-S",
            str(skip_frames),
            "--jpeg",
            "95",
            "--no-banner",
            str(output_path),
        ]
        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        if result.returncode != 0 or not output_path.exists():
            raise RuntimeError("camera capture failed: %s" % result.stdout[-500:])
        return {
            "image_path": str(output_path),
            "image_url": "/uploads/%s" % filename,
            "log": result.stdout,
        }

    def latest_jpeg(self, max_age: float = 3.0) -> Optional[bytes]:
        with self._lock:
            if self._latest_jpeg and time.time() - self._latest_ts <= max_age:
                return bytes(self._latest_jpeg)
        return None

    def stream_error(self) -> str:
        return self._stream_error


class WeatherClient:
    def __init__(self, cache_path: pathlib.Path, timeout: int = 8):
        self.cache_path = pathlib.Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    def current_weather(self, city: str) -> Dict[str, Any]:
        city = (city or os.environ.get("SMART_WARDROBE_CITY") or "Hangzhou").strip()
        cache_key = city.lower()
        cached = self._read_cache().get(cache_key)
        if cached and time.time() - float(cached.get("saved_at", 0)) < 600:
            cached["cached"] = True
            return cached
        try:
            geo = self._geocode(city)
            weather = self._forecast(geo["latitude"], geo["longitude"])
            data = {
                "city": geo.get("name", city),
                "display_name": geo.get("display_name", city),
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
                "temperature_c": weather["temperature_c"],
                "weather_code": weather.get("weather_code"),
                "weather_text": weather_code_text(weather.get("weather_code")),
                "time": weather.get("time", now_iso()),
                "source": "open-meteo",
                "cached": False,
                "saved_at": time.time(),
            }
            cache = self._read_cache()
            cache[cache_key] = data
            self._write_cache(cache)
            return data
        except Exception as exc:
            fallback = {
                "city": city,
                "display_name": city,
                "latitude": None,
                "longitude": None,
                "temperature_c": 26.0,
                "weather_code": None,
                "weather_text": "离线估计",
                "time": now_iso(),
                "source": "fallback",
                "cached": False,
                "error": str(exc),
                "saved_at": time.time(),
            }
            return fallback

    def _geocode(self, city: str) -> Dict[str, Any]:
        query = urllib.parse.urlencode(
            {"name": city, "count": 1, "language": "zh", "format": "json"}
        )
        url = "https://geocoding-api.open-meteo.com/v1/search?%s" % query
        data = self._get_json(url)
        results = data.get("results") or []
        if not results:
            raise RuntimeError("city not found: %s" % city)
        item = results[0]
        display = item.get("name") or city
        if item.get("admin1"):
            display += ", " + item["admin1"]
        if item.get("country"):
            display += ", " + item["country"]
        return {
            "name": item.get("name") or city,
            "display_name": display,
            "latitude": float(item["latitude"]),
            "longitude": float(item["longitude"]),
        }

    def _forecast(self, latitude: float, longitude: float) -> Dict[str, Any]:
        query = urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code",
                "timezone": "auto",
            }
        )
        url = "https://api.open-meteo.com/v1/forecast?%s" % query
        data = self._get_json(url)
        current = data.get("current") or {}
        return {
            "temperature_c": float(current["temperature_2m"]),
            "weather_code": current.get("weather_code"),
            "time": current.get("time", now_iso()),
        }

    def _get_json(self, url: str) -> Dict[str, Any]:
        request = urllib.request.Request(url, headers={"User-Agent": "smart-wardrobe/1.0"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _read_cache(self) -> Dict[str, Any]:
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_cache(self, data: Dict[str, Any]) -> None:
        self.cache_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


class RecommendationEngine:
    def recommend(
        self,
        clothes: List[Dict[str, Any]],
        weather: Dict[str, Any],
        occasion: str = "school",
        limit: int = 3,
    ) -> Dict[str, Any]:
        temp_c = float(weather.get("temperature_c", 26.0))
        target = target_warmth(temp_c)
        season = season_for_temperature(temp_c)
        occasion = (occasion or "school").strip()
        required = ["top", "bottom", "shoes"]
        if temp_c < 20:
            required.append("outer")

        grouped: Dict[str, List[Tuple[float, Dict[str, Any], List[str]]]] = {}
        for item in clothes:
            category = normalize_category(item.get("category"))
            score, reasons = self._score_item(item, temp_c, target, season, occasion)
            grouped.setdefault(category, []).append((score, item, reasons))

        for category in grouped:
            grouped[category].sort(key=lambda entry: entry[0], reverse=True)

        active_categories = [cat for cat in required if grouped.get(cat)]
        if "outer" not in active_categories and temp_c < 16 and grouped.get("outer"):
            active_categories.append("outer")
        if "accessory" not in active_categories and grouped.get("accessory"):
            active_categories.append("accessory")

        missing = [CATEGORY_LABELS.get(cat, cat) for cat in required if not grouped.get(cat)]
        recommendations = []
        if active_categories:
            candidate_lists = [grouped[cat][:4] for cat in active_categories]
            for combo in itertools.product(*candidate_lists):
                items = [entry[1] for entry in combo]
                base_score = sum(entry[0] for entry in combo)
                color_score, color_reason = self._color_score(items)
                total = round(base_score + color_score, 1)
                reasons = [
                    "当前温度 %.1f°C，目标保暖值为 %d/5" % (temp_c, target),
                    "场景为 %s，优先选择场景标签匹配的衣物" % occasion,
                    color_reason,
                ]
                for entry in combo:
                    reasons.extend(entry[2][:2])
                recommendations.append(
                    {
                        "score": total,
                        "items": items,
                        "reason": self._dedupe(reasons)[:8],
                        "summary": self._summary(items, temp_c, occasion),
                    }
                )

        recommendations.sort(key=lambda rec: rec["score"], reverse=True)
        return {
            "weather": weather,
            "occasion": occasion,
            "target_warmth": target,
            "season_hint": season,
            "missing_categories": missing,
            "recommendations": recommendations[:limit],
            "explain": [
                "规则算法会综合温度、场景、季节、保暖值、颜色协调和偏好分。",
                "当前是 MVP 版本，适合比赛演示；后续可以接入用户反馈做轻量学习。",
            ],
        }

    def _score_item(
        self, item: Dict[str, Any], temp_c: float, target: int, season: str, occasion: str
    ) -> Tuple[float, List[str]]:
        warmth = clamp_int(item.get("warmth"), 3, 1, 5)
        favorite = clamp_int(item.get("favorite_score"), 3, 1, 5)
        formality = clamp_int(item.get("formality"), 2, 1, 5)
        seasons = set(split_tags(item.get("season")))
        occasions = set(split_tags(item.get("occasion")))
        material = str(item.get("material") or "").lower()

        score = 40.0 - abs(warmth - target) * 8.0
        reasons = []
        if abs(warmth - target) <= 1:
            score += 12
            reasons.append("%s 的保暖值适合当前温度" % item.get("name"))
        if season in seasons or "all" in seasons or "四季" in seasons:
            score += 10
            reasons.append("%s 的季节标签匹配" % item.get("name"))
        if occasion in occasions or "all" in occasions or "通用" in occasions:
            score += 14
            reasons.append("%s 适合 %s 场景" % (item.get("name"), occasion))
        if temp_c >= 27 and any(token in material for token in LIGHT_MATERIALS):
            score += 6
            reasons.append("%s 的材质更适合偏热天气" % item.get("name"))
        if temp_c <= 12 and any(token in material for token in WARM_MATERIALS):
            score += 6
            reasons.append("%s 的材质更适合偏冷天气" % item.get("name"))
        score += favorite * 2.0
        score -= float(item.get("wear_count") or 0) * 0.4
        if occasion in {"formal", "meeting"}:
            score += formality * 2.0
        return score, reasons or ["%s 可作为备选单品" % item.get("name")]

    def _color_score(self, items: Iterable[Dict[str, Any]]) -> Tuple[float, str]:
        families = [color_family(item.get("color")) for item in items if item.get("color")]
        if not families:
            return 0.0, "颜色信息不足，暂不作为主要依据"
        non_unknown = [family for family in families if family != "unknown"]
        neutral_count = sum(1 for family in non_unknown if family in NEUTRAL_COLOR_FAMILIES)
        unique_count = len(set(non_unknown))
        if neutral_count >= max(1, len(non_unknown) - 1):
            return 10.0, "整体颜色以基础色为主，搭配冲突较低"
        if unique_count <= 2:
            return 7.0, "颜色数量较少，视觉上更统一"
        if unique_count >= 4:
            return -8.0, "颜色种类偏多，已降低推荐分"
        return 2.0, "颜色搭配处于可接受范围"

    def _summary(self, items: List[Dict[str, Any]], temp_c: float, occasion: str) -> str:
        names = " + ".join(str(item.get("name")) for item in items)
        return "%.1f°C / %s：%s" % (temp_c, occasion, names)

    def _dedupe(self, values: Iterable[str]) -> List[str]:
        result = []
        seen = set()
        for value in values:
            if value and value not in seen:
                result.append(value)
                seen.add(value)
        return result


def save_ws63_payload(path: pathlib.Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    data["received_at"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
