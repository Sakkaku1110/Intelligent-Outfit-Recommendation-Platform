#!/usr/bin/env python3
"""Board-camera dataset capture app for the fixed demo wardrobe."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "demo_dataset"
WARDROBE_PATH = ROOT / "demo_wardrobe.json"
DEFAULT_BOARD_URL = "http://192.168.137.2"
CSV_FIELDS = ["sample_id", "image_path", "label_id", "name", "category", "color", "material", "created_at"]


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>智能衣柜数据集采集</title>
  <style>
    :root {
      --bg:#f5f5f7;
      --card:#fff;
      --text:#1d1d1f;
      --muted:#6e6e73;
      --line:#d2d2d7;
      --soft:#e8e8ed;
      --blue:#007aff;
      --green:#34c759;
      --red:#ff3b30;
      --shadow:0 12px 34px rgba(0,0,0,.07);
    }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    main { width:min(1440px,100%); margin:0 auto; padding:22px; }
    header { display:flex; justify-content:space-between; gap:14px; align-items:end; margin-bottom:16px; }
    h1 { margin:0; font-size:32px; letter-spacing:0; }
    h2 { margin:0 0 12px; font-size:21px; letter-spacing:0; }
    p { margin:6px 0 0; color:var(--muted); line-height:1.5; }
    .layout { display:grid; grid-template-columns:minmax(0,1.12fr) minmax(360px,.88fr); gap:16px; align-items:start; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow); overflow:hidden; }
    .panel { padding:16px; }
    .topbar { display:grid; grid-template-columns:1fr 150px; gap:10px; margin-bottom:14px; }
    .stage { position:relative; min-height:420px; background:#050505; overflow:hidden; }
    .stream { display:block; width:100%; height:min(62vh,650px); min-height:420px; object-fit:cover; }
    .finder { position:absolute; inset:10% 16%; border:4px solid rgba(255,255,255,.96); border-radius:14px; box-shadow:0 0 0 999px rgba(0,0,0,.32); pointer-events:none; }
    .stage-footer { position:absolute; left:0; right:0; bottom:0; display:flex; justify-content:space-between; align-items:center; gap:10px; padding:14px; background:linear-gradient(180deg,rgba(0,0,0,0),rgba(0,0,0,.76)); color:white; }
    .hint { font-size:14px; opacity:.9; }
    button, select, input { min-height:48px; border-radius:12px; font:inherit; }
    button { border:0; background:var(--blue); color:white; font-weight:800; cursor:pointer; padding:0 18px; }
    button.secondary { background:var(--soft); color:var(--text); }
    button.green { background:var(--green); color:#061b0c; }
    button.red { background:#ffe7e5; color:var(--red); }
    button.ghost { background:#f5f5f7; color:var(--text); border:1px solid var(--line); }
    button:disabled { opacity:.52; cursor:wait; }
    label { display:grid; gap:7px; color:var(--muted); font-size:14px; }
    select, input { width:100%; padding:0 13px; color:var(--text); background:#fbfbfd; border:1px solid var(--line); }
    .review { display:grid; gap:12px; }
    .review.empty { min-height:300px; place-items:center; color:var(--muted); text-align:center; background:linear-gradient(180deg,#fff,#fafafa); }
    .preview { width:100%; aspect-ratio:4/3; object-fit:cover; border:1px solid var(--line); border-radius:14px; background:#f2f2f2; }
    .actions { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .actions.three { grid-template-columns:repeat(3,minmax(0,1fr)); }
    .status { min-height:24px; color:var(--muted); margin-top:10px; white-space:pre-wrap; }
    .stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:16px; }
    .stat { padding:12px; border:1px solid var(--line); border-radius:14px; background:#fff; }
    .stat strong { display:block; font-size:24px; }
    .stat span { color:var(--muted); font-size:12px; }
    .library { margin-top:16px; }
    .library-head { display:flex; gap:10px; justify-content:space-between; align-items:center; margin-bottom:10px; }
    .sample-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
    .sample { border:1px solid var(--line); border-radius:14px; overflow:hidden; background:#fff; }
    .sample img { width:100%; aspect-ratio:1/1; object-fit:cover; display:block; background:#eee; }
    .sample-body { padding:10px; display:grid; gap:8px; }
    .sample-title { font-weight:800; line-height:1.25; }
    .sample-meta { color:var(--muted); font-size:12px; }
    .sample-actions { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
    .pill { display:inline-flex; align-items:center; min-height:30px; padding:0 10px; border-radius:999px; background:#eef5ff; color:#0a62c4; font-weight:800; font-size:12px; }
    dialog { width:min(520px,calc(100% - 28px)); border:0; border-radius:18px; padding:0; box-shadow:0 22px 70px rgba(0,0,0,.24); }
    dialog::backdrop { background:rgba(0,0,0,.28); }
    .dialog-body { padding:16px; display:grid; gap:12px; }
    @media (max-width:1080px) {
      .layout { grid-template-columns:1fr; }
      .sample-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
    }
    @media (max-width:640px) {
      main { padding:14px; }
      header { display:block; }
      h1 { font-size:28px; }
      .topbar, .actions, .actions.three { grid-template-columns:1fr; }
      .sample-grid, .stats { grid-template-columns:1fr; }
      .stream, .stage { min-height:360px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>数据集采集</h1>
        <p>调用板子摄像头实时取景，点确认拍照后进入人工审核。只有确认录入的照片才会进入训练数据集。</p>
      </div>
      <button id="refreshBtn" class="secondary" type="button">刷新</button>
    </header>

    <section class="topbar">
      <label>
        板子地址
        <input id="boardUrl" placeholder="http://192.168.137.2" />
      </label>
      <button id="saveBoardBtn" class="secondary" type="button">连接板子</button>
    </section>

    <section class="layout">
      <section class="card">
        <div class="stage">
          <img id="stream" class="stream" alt="板子摄像头实时画面" />
          <div class="finder"></div>
          <div class="stage-footer">
            <span id="cameraHint" class="hint">把衣服放进取景框，尽量占满 70% 画面</span>
            <button id="captureBtn" type="button">确认拍照</button>
          </div>
        </div>
        <div class="panel">
          <label>
            本次采集标签
            <select id="labelSelect"></select>
          </label>
          <div class="status" id="status"></div>
        </div>
      </section>

      <aside class="card panel">
        <h2>人工审核</h2>
        <div id="reviewEmpty" class="review empty">
          <div>
            <strong>还没有待审核照片</strong>
            <p>点击左侧“确认拍照”后，会在这里检查裁剪结果、修改标签，然后决定是否录入。</p>
          </div>
        </div>
        <div id="reviewBox" class="review" hidden>
          <img id="draftPreview" class="preview" alt="待审核照片" />
          <label>
            审核后标签
            <select id="draftLabel"></select>
          </label>
          <div class="actions">
            <button id="commitBtn" class="green" type="button">确认录入</button>
            <button id="rejectBtn" class="red" type="button">丢弃重拍</button>
          </div>
          <span id="draftInfo" class="pill"></span>
        </div>
      </aside>
    </section>

    <section class="stats" id="counts"></section>

    <section class="library">
      <div class="library-head">
        <div>
          <h2>样本库</h2>
          <p>这里支持查询、修改标签、删除样本。修改后训练会使用新的标签。</p>
        </div>
        <div class="actions">
          <button id="trainBtn" type="button">训练模型</button>
          <button id="deployBtn" class="secondary" type="button">推送到板子</button>
        </div>
      </div>
      <div id="samples" class="sample-grid"></div>
    </section>
  </main>

  <dialog id="editDialog">
    <div class="dialog-body">
      <h2>修改样本</h2>
      <img id="editPreview" class="preview" alt="编辑样本" />
      <label>
        样本标签
        <select id="editLabel"></select>
      </label>
      <div class="actions">
        <button id="saveEditBtn" type="button">保存修改</button>
        <button id="closeEditBtn" class="secondary" type="button">取消</button>
      </div>
    </div>
  </dialog>

  <script>
    let labels = [];
    let samples = [];
    let currentDraft = null;
    let editingSample = null;
    const $ = (id) => document.querySelector(id);

    async function api(path, options = {}) {
      const res = await fetch(path, { ...options, headers: { "Content-Type":"application/json", ...(options.headers || {}) } });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }

    function labelOption(item) {
      const category = item.category_label || item.category;
      const color = item.color_label || item.color;
      const material = item.material_label || item.material;
      return `<option value="${item.id}">${item.name} / ${category} / ${color} / ${material}</option>`;
    }

    function setStatus(message) {
      $("#status").textContent = message || "";
    }

    function refreshStream() {
      $("#stream").src = `/api/board/stream?t=${Date.now()}`;
    }

    async function loadState() {
      const data = await api("/api/state");
      labels = data.labels;
      samples = data.samples;
      $("#boardUrl").value = data.board_url || "";
      const options = labels.map(labelOption).join("");
      $("#labelSelect").innerHTML = options;
      $("#draftLabel").innerHTML = options;
      $("#editLabel").innerHTML = options;
      renderCounts();
      renderSamples();
    }

    function renderCounts() {
      $("#counts").innerHTML = labels.map((item) => `
        <div class="stat">
          <strong>${item.count || 0}</strong>
          <span>${item.name}</span>
        </div>
      `).join("");
    }

    function renderSamples() {
      if (!samples.length) {
        $("#samples").innerHTML = `<div class="card panel"><p>还没有样本。先用左侧板子摄像头拍几张。</p></div>`;
        return;
      }
      $("#samples").innerHTML = samples.map((sample) => `
        <article class="sample" data-id="${sample.sample_id}">
          <img src="${sample.image_url}?t=${Date.now()}" alt="${sample.name}" />
          <div class="sample-body">
            <div>
              <div class="sample-title">${sample.name}</div>
              <div class="sample-meta">${sample.category_label || sample.category} / ${sample.color_label || sample.color} / ${sample.material_label || sample.material}</div>
            </div>
            <div class="sample-actions">
              <button class="ghost editSample" type="button" data-id="${sample.sample_id}">修改</button>
              <button class="red deleteSample" type="button" data-id="${sample.sample_id}">删除</button>
            </div>
          </div>
        </article>
      `).join("");
      document.querySelectorAll(".editSample").forEach((btn) => btn.addEventListener("click", () => openEdit(btn.dataset.id)));
      document.querySelectorAll(".deleteSample").forEach((btn) => btn.addEventListener("click", () => deleteSample(btn.dataset.id)));
    }

    async function saveBoardUrl() {
      const boardUrl = $("#boardUrl").value.trim();
      await api("/api/config", { method:"PUT", body:JSON.stringify({ board_url:boardUrl }) });
      setStatus("板子地址已更新，正在重连摄像头...");
      refreshStream();
      await loadState();
    }

    async function captureFromBoard() {
      $("#captureBtn").disabled = true;
      setStatus("正在调用板子摄像头拍照...");
      try {
        const labelId = $("#labelSelect").value;
        const data = await api("/api/board/capture", {
          method:"POST",
          body:JSON.stringify({ label_id:labelId, resolution:"640x480", skip_frames:10 })
        });
        currentDraft = data.draft;
        $("#draftPreview").src = currentDraft.image_url + "?t=" + Date.now();
        $("#draftLabel").value = currentDraft.label_id;
        $("#draftInfo").textContent = "待审核：" + currentDraft.name;
        $("#reviewEmpty").hidden = true;
        $("#reviewBox").hidden = false;
        setStatus("拍照完成。请在右侧审核，确认后才会录入数据集。");
      } catch (err) {
        setStatus("拍照失败：" + err.message);
      } finally {
        $("#captureBtn").disabled = false;
      }
    }

    async function commitDraft() {
      if (!currentDraft) return;
      $("#commitBtn").disabled = true;
      setStatus("正在录入审核通过的照片...");
      try {
        await api("/api/samples", {
          method:"POST",
          body:JSON.stringify({ draft_id:currentDraft.draft_id, label_id:$("#draftLabel").value })
        });
        currentDraft = null;
        $("#reviewEmpty").hidden = false;
        $("#reviewBox").hidden = true;
        await loadState();
        setStatus("已录入数据集。可以继续拍下一张。");
      } catch (err) {
        setStatus("录入失败：" + err.message);
      } finally {
        $("#commitBtn").disabled = false;
      }
    }

    async function rejectDraft() {
      if (!currentDraft) return;
      $("#rejectBtn").disabled = true;
      try {
        await api(`/api/drafts/${encodeURIComponent(currentDraft.draft_id)}`, { method:"DELETE" });
        currentDraft = null;
        $("#reviewEmpty").hidden = false;
        $("#reviewBox").hidden = true;
        setStatus("已丢弃这张照片，可以重拍。");
      } catch (err) {
        setStatus("丢弃失败：" + err.message);
      } finally {
        $("#rejectBtn").disabled = false;
      }
    }

    function openEdit(sampleId) {
      editingSample = samples.find((sample) => sample.sample_id === sampleId);
      if (!editingSample) return;
      $("#editPreview").src = editingSample.image_url + "?t=" + Date.now();
      $("#editLabel").value = editingSample.label_id;
      $("#editDialog").showModal();
    }

    async function saveEdit() {
      if (!editingSample) return;
      $("#saveEditBtn").disabled = true;
      try {
        await api(`/api/samples/${encodeURIComponent(editingSample.sample_id)}`, {
          method:"PUT",
          body:JSON.stringify({ label_id:$("#editLabel").value })
        });
        $("#editDialog").close();
        editingSample = null;
        await loadState();
        setStatus("样本标签已修改。");
      } catch (err) {
        setStatus("修改失败：" + err.message);
      } finally {
        $("#saveEditBtn").disabled = false;
      }
    }

    async function deleteSample(sampleId) {
      if (!confirm("确定删除这张样本吗？")) return;
      await api(`/api/samples/${encodeURIComponent(sampleId)}`, { method:"DELETE" });
      await loadState();
      setStatus("样本已删除。");
    }

    async function runTrain() {
      $("#trainBtn").disabled = true;
      setStatus("正在训练模型...");
      try {
        const result = await api("/api/train", { method:"POST", body:"{}" });
        setStatus(result.output || "训练完成");
      } catch (err) {
        setStatus("训练失败：" + err.message);
      } finally {
        $("#trainBtn").disabled = false;
      }
    }

    async function deploy() {
      $("#deployBtn").disabled = true;
      setStatus("正在推送模型到板子...");
      try {
        const result = await api("/api/deploy", { method:"POST", body:"{}" });
        setStatus(result.output || "已推送到板子");
      } catch (err) {
        setStatus("推送失败：" + err.message);
      } finally {
        $("#deployBtn").disabled = false;
      }
    }

    $("#refreshBtn").addEventListener("click", async () => { await loadState(); refreshStream(); });
    $("#saveBoardBtn").addEventListener("click", saveBoardUrl);
    $("#captureBtn").addEventListener("click", captureFromBoard);
    $("#commitBtn").addEventListener("click", commitDraft);
    $("#rejectBtn").addEventListener("click", rejectDraft);
    $("#saveEditBtn").addEventListener("click", saveEdit);
    $("#closeEditBtn").addEventListener("click", () => $("#editDialog").close());
    $("#trainBtn").addEventListener("click", runTrain);
    $("#deployBtn").addEventListener("click", deploy);

    loadState().then(refreshStream).catch((err) => setStatus(err.message));
  </script>
</body>
</html>
"""


class DatasetStudioHandler(BaseHTTPRequestHandler):
    dataset_dir = DEFAULT_DATASET
    board_url = DEFAULT_BOARD_URL

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

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/":
                self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/state":
                self.send_json(self.state_payload())
            elif path == "/api/board/stream":
                self.proxy_board_stream()
            elif path.startswith("/media/"):
                rel_path = urllib.parse.unquote(path.removeprefix("/media/"))
                self.serve_dataset_file(rel_path)
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/board/capture":
                self.send_json(self.capture_board_draft(self.read_json()))
            elif path == "/api/samples":
                self.send_json(self.commit_sample(self.read_json()), HTTPStatus.CREATED)
            elif path == "/api/upload":
                self.send_json(self.upload_image_data(self.read_json()), HTTPStatus.CREATED)
            elif path == "/api/train":
                self.send_json(self.run_script("train_demo_model.py"))
            elif path == "/api/deploy":
                self.send_json(self.run_script("deploy_demo_model.py", "--restart"))
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_PUT(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/config":
                payload = self.read_json()
                self.__class__.board_url = self.clean_board_url(payload.get("board_url") or self.board_url)
                self.send_json({"board_url": self.board_url})
            elif path.startswith("/api/samples/"):
                sample_id = urllib.parse.unquote(path.rsplit("/", 1)[-1])
                self.send_json(self.update_sample(sample_id, self.read_json()))
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path.startswith("/api/samples/"):
                sample_id = urllib.parse.unquote(path.rsplit("/", 1)[-1])
                self.send_json(self.delete_sample(sample_id))
            elif path.startswith("/api/drafts/"):
                draft_id = urllib.parse.unquote(path.rsplit("/", 1)[-1])
                self.send_json(self.delete_draft(draft_id))
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def wardrobe(self) -> list[dict[str, Any]]:
        return json.loads(WARDROBE_PATH.read_text(encoding="utf-8"))["items"]

    def wardrobe_by_id(self) -> dict[str, dict[str, Any]]:
        return {item["id"]: item for item in self.wardrobe()}

    def labels_path(self) -> Path:
        return self.dataset_dir / "labels.csv"

    def drafts_dir(self) -> Path:
        path = self.dataset_dir / "drafts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def clean_board_url(value: Any) -> str:
        text = str(value or "").strip().rstrip("/")
        if not text:
            return DEFAULT_BOARD_URL
        if not text.startswith(("http://", "https://")):
            text = "http://" + text
        return text

    def sample_id_from_path(self, image_path: str) -> str:
        stem = Path(image_path).stem
        return stem or "sample_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    def read_rows(self) -> list[dict[str, str]]:
        labels_path = self.labels_path()
        if not labels_path.exists():
            return []
        rows: list[dict[str, str]] = []
        for row in csv.DictReader(labels_path.open("r", encoding="utf-8-sig")):
            normalized = {field: str(row.get(field, "") or "") for field in CSV_FIELDS}
            if not normalized["sample_id"]:
                normalized["sample_id"] = self.sample_id_from_path(normalized["image_path"])
            if not normalized["created_at"]:
                normalized["created_at"] = ""
            rows.append(normalized)
        return rows

    def write_rows(self, rows: list[dict[str, str]]) -> None:
        labels_path = self.labels_path()
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        with labels_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})

    def label_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.read_rows():
            label_id = row.get("label_id", "")
            counts[label_id] = counts.get(label_id, 0) + 1
        return counts

    def state_payload(self) -> dict[str, Any]:
        counts = self.label_counts()
        labels = []
        for item in self.wardrobe():
            entry = dict(item)
            entry["count"] = counts.get(item["id"], 0)
            labels.append(entry)
        return {
            "labels": labels,
            "samples": self.sample_payloads(),
            "dataset": str(self.dataset_dir),
            "board_url": self.board_url,
        }

    def sample_payloads(self) -> list[dict[str, Any]]:
        payloads = []
        for row in self.read_rows():
            item = self.wardrobe_by_id().get(row["label_id"], {})
            entry = dict(row)
            entry["name"] = row.get("name") or item.get("name", row["label_id"])
            entry["category"] = row.get("category") or item.get("category", "")
            entry["color"] = row.get("color") or item.get("color", "")
            entry["material"] = row.get("material") or item.get("material", "")
            entry["category_label"] = item.get("category_label", entry["category"])
            entry["color_label"] = item.get("color_label", entry["color"])
            entry["material_label"] = item.get("material_label", entry["material"])
            entry["image_url"] = "/media/" + urllib.parse.quote(row["image_path"].replace("\\", "/"))
            payloads.append(entry)
        return list(reversed(payloads))

    def label_for_payload(self, label_id: str) -> dict[str, Any]:
        item = self.wardrobe_by_id().get(label_id)
        if not item:
            raise ValueError("unknown label_id: %s" % label_id)
        return item

    def append_sample_row(self, label_id: str, image_path: Path, sample_id: str) -> dict[str, Any]:
        item = self.label_for_payload(label_id)
        row = {
            "sample_id": sample_id,
            "image_path": str(image_path.relative_to(self.dataset_dir)).replace("\\", "/"),
            "label_id": label_id,
            "name": str(item["name"]),
            "category": str(item["category"]),
            "color": str(item["color"]),
            "material": str(item["material"]),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        rows = self.read_rows()
        rows.append(row)
        self.write_rows(rows)
        return {"sample": row, "count": self.label_counts().get(label_id, 0)}

    def capture_board_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        label_id = str(payload.get("label_id") or "")
        item = self.label_for_payload(label_id)
        response = self.post_board_json(
            "/api/clothes/capture/analyze",
            {
                "use_viewfinder": True,
                "resolution": payload.get("resolution") or "640x480",
                "skip_frames": int(payload.get("skip_frames") or 10),
            },
        )
        capture = response.get("capture") or {}
        image_url = str(capture.get("image_url") or "")
        if not image_url:
            raise ValueError("board capture did not return image_url")
        image_bytes = self.get_board_bytes(image_url)
        draft_id = "draft_%s" % datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        draft_path = self.drafts_dir() / ("%s.jpg" % draft_id)
        draft_path.write_bytes(image_bytes)
        meta = {
            "draft_id": draft_id,
            "label_id": label_id,
            "name": item["name"],
            "category": item["category"],
            "color": item["color"],
            "material": item["material"],
            "image_path": str(draft_path.relative_to(self.dataset_dir)).replace("\\", "/"),
            "image_url": "/media/" + urllib.parse.quote(str(draft_path.relative_to(self.dataset_dir)).replace("\\", "/")),
            "board_capture": capture,
            "analysis": response.get("analysis") or {},
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        (draft_path.with_suffix(".json")).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"draft": meta}

    def commit_sample(self, payload: dict[str, Any]) -> dict[str, Any]:
        draft_id = str(payload.get("draft_id") or "")
        label_id = str(payload.get("label_id") or "")
        item = self.label_for_payload(label_id)
        draft_path = self.drafts_dir() / ("%s.jpg" % draft_id)
        if not draft_path.exists():
            raise ValueError("draft not found: %s" % draft_id)
        sample_id = "%s_%s" % (label_id, datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        image_dir = self.dataset_dir / "images" / label_id
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / ("%s.jpg" % sample_id)
        shutil.move(str(draft_path), str(image_path))
        meta_path = draft_path.with_suffix(".json")
        if meta_path.exists():
            meta_path.unlink()
        result = self.append_sample_row(label_id, image_path, sample_id)
        result["sample"]["name"] = item["name"]
        return result

    def upload_image_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        label_id = str(payload.get("label_id") or "")
        self.label_for_payload(label_id)
        image_data = str(payload.get("image_data") or "")
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
        sample_id = "%s_%s" % (label_id, datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        image_dir = self.dataset_dir / "images" / label_id
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / ("%s.jpg" % sample_id)
        image_path.write_bytes(image_bytes)
        return self.append_sample_row(label_id, image_path, sample_id)

    def update_sample(self, sample_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self.read_rows()
        item_index = next((index for index, row in enumerate(rows) if row["sample_id"] == sample_id), -1)
        if item_index < 0:
            raise ValueError("sample not found: %s" % sample_id)
        row = rows[item_index]
        new_label_id = str(payload.get("label_id") or row["label_id"])
        item = self.label_for_payload(new_label_id)
        old_path = self.dataset_dir / row["image_path"]
        if new_label_id != row["label_id"] and old_path.exists():
            new_dir = self.dataset_dir / "images" / new_label_id
            new_dir.mkdir(parents=True, exist_ok=True)
            new_path = new_dir / old_path.name
            if new_path.exists():
                new_path = new_dir / ("%s_%s%s" % (old_path.stem, datetime.now().strftime("%H%M%S_%f"), old_path.suffix))
            shutil.move(str(old_path), str(new_path))
            row["image_path"] = str(new_path.relative_to(self.dataset_dir)).replace("\\", "/")
        row.update(
            {
                "label_id": new_label_id,
                "name": str(item["name"]),
                "category": str(item["category"]),
                "color": str(item["color"]),
                "material": str(item["material"]),
            }
        )
        rows[item_index] = row
        self.write_rows(rows)
        return {"sample": row}

    def delete_sample(self, sample_id: str) -> dict[str, Any]:
        rows = self.read_rows()
        kept = []
        deleted_row = None
        for row in rows:
            if row["sample_id"] == sample_id:
                deleted_row = row
            else:
                kept.append(row)
        if not deleted_row:
            raise ValueError("sample not found: %s" % sample_id)
        image_path = self.dataset_dir / deleted_row["image_path"]
        if image_path.exists():
            image_path.unlink()
        self.write_rows(kept)
        return {"deleted": True, "sample_id": sample_id}

    def delete_draft(self, draft_id: str) -> dict[str, Any]:
        deleted = False
        for path in [self.drafts_dir() / ("%s.jpg" % draft_id), self.drafts_dir() / ("%s.json" % draft_id)]:
            if path.exists():
                path.unlink()
                deleted = True
        return {"deleted": deleted}

    def post_board_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self.board_url + path
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=18) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError("cannot reach board %s: %s" % (self.board_url, exc)) from exc

    def get_board_bytes(self, path_or_url: str) -> bytes:
        url = path_or_url if path_or_url.startswith(("http://", "https://")) else self.board_url + path_or_url
        try:
            with urllib.request.urlopen(url, timeout=18) as response:
                return response.read()
        except urllib.error.URLError as exc:
            raise RuntimeError("cannot download board image: %s" % exc) from exc

    def proxy_board_stream(self) -> None:
        url = self.board_url + "/api/camera/stream"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                content_type = response.headers.get("Content-Type") or "multipart/x-mixed-replace; boundary=smartwardrobe"
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.end_headers()
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except urllib.error.URLError as exc:
            self.send_json({"error": "cannot open board camera stream: %s" % exc}, HTTPStatus.BAD_GATEWAY)

    def serve_dataset_file(self, relative_path: str) -> None:
        safe = (self.dataset_dir / relative_path).resolve()
        root = self.dataset_dir.resolve()
        if root not in safe.parents and safe != root:
            self.send_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        if not safe.exists() or not safe.is_file():
            self.send_json({"error": "file not found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = "image/jpeg" if safe.suffix.lower() in {".jpg", ".jpeg"} else "application/octet-stream"
        self.send_bytes(safe.read_bytes(), content_type)

    def run_script(self, script_name: str, *extra: str) -> dict[str, str]:
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

    def send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        self.send_bytes(
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

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
    parser.add_argument("--board-url", default=DEFAULT_BOARD_URL)
    args = parser.parse_args()

    DatasetStudioHandler.dataset_dir = Path(args.dataset)
    DatasetStudioHandler.dataset_dir.mkdir(parents=True, exist_ok=True)
    DatasetStudioHandler.board_url = DatasetStudioHandler.clean_board_url(args.board_url)
    server = ThreadingHTTPServer((args.host, args.port), DatasetStudioHandler)
    print("Dataset studio: http://%s:%d" % (args.host, args.port), flush=True)
    print("Board camera: %s" % DatasetStudioHandler.board_url, flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
