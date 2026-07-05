#!/usr/bin/env python3
"""Browser-based dataset capture app for the fixed demo wardrobe."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import subprocess
import sys
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "demo_dataset"
WARDROBE_PATH = ROOT / "demo_wardrobe.json"


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>智能衣柜数据集采集</title>
  <style>
    :root { --bg:#f5f5f7; --card:#fff; --text:#1d1d1f; --muted:#6e6e73; --line:#d2d2d7; --blue:#007aff; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    main { width:min(1180px,100%); margin:0 auto; padding:18px; }
    header { display:flex; justify-content:space-between; gap:12px; align-items:end; margin-bottom:12px; }
    h1 { margin:0; font-size:30px; letter-spacing:0; }
    p { margin:4px 0 0; color:var(--muted); }
    .layout { display:grid; grid-template-columns:minmax(0,1.15fr) minmax(300px,.85fr); gap:14px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:8px; box-shadow:0 8px 24px rgba(0,0,0,.05); }
    .stage { overflow:hidden; }
    .video-wrap { position:relative; background:#111; min-height:360px; }
    video { display:block; width:100%; height:min(70vh,680px); object-fit:cover; }
    .finder { position:absolute; inset:10% 16%; border:3px solid #fff; border-radius:8px; box-shadow:0 0 0 999px rgba(0,0,0,.25); pointer-events:none; }
    .actions { display:grid; grid-template-columns:1fr 1fr; gap:10px; padding:12px; }
    .stage .actions { grid-template-columns:repeat(3,minmax(0,1fr)); }
    button, select { min-height:48px; border:0; border-radius:8px; font:inherit; }
    button { background:var(--blue); color:white; font-weight:700; cursor:pointer; }
    button.secondary { background:#e8e8ed; color:var(--text); }
    button:disabled { opacity:.55; cursor:wait; }
    aside { padding:12px; }
    label { display:grid; gap:6px; color:var(--muted); font-size:13px; margin-bottom:10px; }
    select { width:100%; padding:0 12px; color:var(--text); background:#fbfbfd; border:1px solid var(--line); }
    .preview { width:100%; aspect-ratio:4/3; object-fit:cover; border:1px solid var(--line); border-radius:8px; background:#f2f2f2; }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-top:12px; }
    .item { padding:10px; border:1px solid var(--line); border-radius:8px; background:#fbfbfd; }
    .item strong { display:block; }
    .item span { color:var(--muted); font-size:12px; }
    .status { min-height:24px; color:var(--muted); margin-top:10px; }
    @media (max-width:820px){ .layout{grid-template-columns:1fr;} video{height:58vh;} }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>数据集采集</h1>
        <p>选标签，拍取景框内裁剪图，每件衣物建议 8-12 张。</p>
      </div>
      <button id="refreshBtn" class="secondary" type="button">刷新统计</button>
    </header>
    <section class="layout">
      <section class="card stage">
        <div class="video-wrap">
          <video id="video" playsinline autoplay muted></video>
          <div class="finder"></div>
        </div>
        <div class="actions">
          <button id="captureBtn" type="button">拍摄并上传</button>
          <button id="fileBtn" class="secondary" type="button">手机拍照上传</button>
          <button id="switchBtn" class="secondary" type="button">切换摄像头</button>
        </div>
      </section>
      <aside class="card">
        <label>
          当前衣物标签
          <select id="labelSelect"></select>
        </label>
        <img id="preview" class="preview" alt="preview" />
        <div class="actions">
          <button id="trainBtn" type="button">训练模型</button>
          <button id="deployBtn" class="secondary" type="button">推送到板子</button>
        </div>
        <div id="status" class="status"></div>
        <div id="counts" class="grid"></div>
      </aside>
    </section>
  </main>
  <canvas id="canvas" hidden></canvas>
  <input id="fileInput" type="file" accept="image/*" capture="environment" hidden />
  <script>
    let labels = [];
    let stream = null;
    let facingMode = "environment";
    const $ = (id) => document.querySelector(id);

    async function api(path, options = {}) {
      const res = await fetch(path, { ...options, headers: { "Content-Type":"application/json", ...(options.headers || {}) } });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }

    async function startCamera() {
      if (stream) stream.getTracks().forEach((track) => track.stop());
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode, width: { ideal: 1280 }, height: { ideal: 720 } }, audio:false });
      $("#video").srcObject = stream;
    }

    function cropFrame() {
      const video = $("#video");
      const canvas = $("#canvas");
      const w = video.videoWidth;
      const h = video.videoHeight;
      const x = Math.floor(w * 0.16);
      const y = Math.floor(h * 0.10);
      const cw = Math.floor(w * 0.68);
      const ch = Math.floor(h * 0.80);
      canvas.width = 900;
      canvas.height = Math.round(900 * ch / cw);
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, x, y, cw, ch, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", 0.92);
    }

    async function cropImageFile(file) {
      const img = new Image();
      img.src = URL.createObjectURL(file);
      await img.decode();
      const canvas = $("#canvas");
      const w = img.naturalWidth;
      const h = img.naturalHeight;
      const x = Math.floor(w * 0.16);
      const y = Math.floor(h * 0.10);
      const cw = Math.floor(w * 0.68);
      const ch = Math.floor(h * 0.80);
      canvas.width = 900;
      canvas.height = Math.round(900 * ch / cw);
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, x, y, cw, ch, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(img.src);
      return canvas.toDataURL("image/jpeg", 0.92);
    }

    async function loadState() {
      const data = await api("/api/state");
      labels = data.labels;
      $("#labelSelect").innerHTML = labels.map((item) => `<option value="${item.id}">${item.name} / ${item.color_label} / ${item.category}</option>`).join("");
      $("#counts").innerHTML = labels.map((item) => `<div class="item"><strong>${item.name}</strong><span>${item.count || 0} 张</span></div>`).join("");
    }

    async function uploadImageData(imageData) {
      const labelId = $("#labelSelect").value;
      const label = labels.find((item) => item.id === labelId);
      $("#preview").src = imageData;
      $("#status").textContent = "上传中...";
      const result = await api("/api/upload", { method:"POST", body: JSON.stringify({ label_id: labelId, image_data: imageData }) });
      $("#status").textContent = `已保存 ${label.name}：${result.count} 张`;
      await loadState();
    }

    async function captureUpload() {
      const imageData = cropFrame();
      $("#captureBtn").disabled = true;
      try {
        await uploadImageData(imageData);
      } finally {
        $("#captureBtn").disabled = false;
      }
    }

    async function fileUpload(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      $("#fileBtn").disabled = true;
      try {
        const imageData = await cropImageFile(file);
        await uploadImageData(imageData);
      } finally {
        $("#fileBtn").disabled = false;
        event.target.value = "";
      }
    }

    async function runTrain() {
      $("#status").textContent = "训练中...";
      $("#trainBtn").disabled = true;
      try {
        const result = await api("/api/train", { method:"POST", body:"{}" });
        $("#status").textContent = result.output || "训练完成";
      } finally {
        $("#trainBtn").disabled = false;
      }
    }

    async function deploy() {
      $("#status").textContent = "推送到板子...";
      $("#deployBtn").disabled = true;
      try {
        const result = await api("/api/deploy", { method:"POST", body:"{}" });
        $("#status").textContent = result.output || "已推送";
      } finally {
        $("#deployBtn").disabled = false;
      }
    }

    $("#captureBtn").addEventListener("click", captureUpload);
    $("#fileBtn").addEventListener("click", () => $("#fileInput").click());
    $("#fileInput").addEventListener("change", fileUpload);
    $("#switchBtn").addEventListener("click", async () => { facingMode = facingMode === "environment" ? "user" : "environment"; await startCamera(); });
    $("#refreshBtn").addEventListener("click", loadState);
    $("#trainBtn").addEventListener("click", runTrain);
    $("#deployBtn").addEventListener("click", deploy);
    loadState();
    startCamera().catch((err) => { $("#status").textContent = err.message; });
  </script>
</body>
</html>
"""


class DatasetStudioHandler(BaseHTTPRequestHandler):
    dataset_dir = DEFAULT_DATASET

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/state":
            self.send_json(self.state_payload())
        else:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/upload":
                self.send_json(self.upload(self.read_json()))
            elif path == "/api/train":
                self.send_json(self.run_script("train_demo_model.py"))
            elif path == "/api/deploy":
                self.send_json(self.run_script("deploy_demo_model.py", "--restart"))
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def wardrobe(self) -> list[dict]:
        return json.loads(WARDROBE_PATH.read_text(encoding="utf-8"))["items"]

    def label_counts(self) -> dict[str, int]:
        labels_path = self.dataset_dir / "labels.csv"
        counts: dict[str, int] = {}
        if not labels_path.exists():
            return counts
        for row in csv.DictReader(labels_path.open("r", encoding="utf-8-sig")):
            counts[row.get("label_id", "")] = counts.get(row.get("label_id", ""), 0) + 1
        return counts

    def state_payload(self) -> dict:
        counts = self.label_counts()
        labels = []
        for item in self.wardrobe():
            entry = dict(item)
            entry["count"] = counts.get(item["id"], 0)
            labels.append(entry)
        return {"labels": labels, "dataset": str(self.dataset_dir)}

    def upload(self, payload: dict) -> dict:
        label_id = str(payload.get("label_id") or "")
        item = next((entry for entry in self.wardrobe() if entry["id"] == label_id), None)
        if not item:
            raise ValueError("unknown label_id: %s" % label_id)
        image_data = str(payload.get("image_data") or "")
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
        image_dir = self.dataset_dir / "images" / label_id
        image_dir.mkdir(parents=True, exist_ok=True)
        filename = "%s_%s.jpg" % (label_id, datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        image_path = image_dir / filename
        image_path.write_bytes(image_bytes)
        labels_path = self.dataset_dir / "labels.csv"
        is_new = not labels_path.exists()
        with labels_path.open("a", newline="", encoding="utf-8-sig") as file:
            fieldnames = ["image_path", "label_id", "name", "category", "color", "material"]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if is_new:
                writer.writeheader()
            writer.writerow(
                {
                    "image_path": str(image_path.relative_to(self.dataset_dir)).replace("\\", "/"),
                    "label_id": label_id,
                    "name": item["name"],
                    "category": item["category"],
                    "color": item["color"],
                    "material": item["material"],
                }
            )
        return {"saved": str(image_path), "count": self.label_counts().get(label_id, 0)}

    def run_script(self, script_name: str, *extra: str) -> dict:
        script = ROOT / script_name
        if script_name == "deploy_demo_model.py":
            command = [
                sys.executable,
                str(script),
                "--model",
                str(self.dataset_dir / "vision_model.json"),
                *extra,
            ]
        else:
            command = [sys.executable, str(script), "--dataset", str(self.dataset_dir), *extra]
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout[-1200:])
        return {"output": result.stdout.strip()}

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        self.send_bytes(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8", status)

    def send_bytes(self, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    args = parser.parse_args()

    DatasetStudioHandler.dataset_dir = Path(args.dataset)
    DatasetStudioHandler.dataset_dir.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), DatasetStudioHandler)
    print("Dataset studio: http://%s:%d" % (args.host, args.port), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
