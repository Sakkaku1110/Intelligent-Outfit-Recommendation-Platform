const CATEGORY_LABELS = {
  top: "上衣",
  bottom: "裤子",
  outer: "外套",
  shoes: "鞋子",
  accessory: "配饰",
  auto: "自动",
};

const DEFAULT_NAMES = {
  top: "新上衣",
  bottom: "新裤子",
  outer: "新外套",
  shoes: "新鞋子",
  accessory: "新配饰",
};

const state = {
  apiBase: defaultApiBase(),
  health: null,
  clothes: [],
  recommendation: null,
  pendingDraft: null,
  pendingAnalysis: null,
  pendingCapture: null,
  busy: false,
};

const els = {
  status: document.querySelector("#statusPill"),
  temp: document.querySelector("#tempMetric"),
  count: document.querySelector("#countMetric"),
  camera: document.querySelector("#cameraMetric"),
  city: document.querySelector("#cityInput"),
  occasion: document.querySelector("#occasionSelect"),
  weatherLine: document.querySelector("#weatherLine"),
  todayTitle: document.querySelector("#todayTitle"),
  todaySummary: document.querySelector("#todaySummary"),
  refresh: document.querySelector("#refreshBtn"),
  closetRefresh: document.querySelector("#closetRefreshBtn"),
  mirrorPanel: document.querySelector("#mirrorPanel"),
  recommendList: document.querySelector("#recommendList"),
  wardrobeGrid: document.querySelector("#wardrobeGrid"),
  cameraStream: document.querySelector("#cameraStream"),
  analyzeCaptureBtn: document.querySelector("#analyzeCaptureBtn"),
  pipelineChip: document.querySelector("#pipelineChip"),
  cloudStatus: document.querySelector("#cloudStatus"),
  reviewTitle: document.querySelector("#reviewTitle"),
  reviewImage: document.querySelector("#reviewImage"),
  reviewBadge: document.querySelector("#reviewBadge"),
  cloudDetail: document.querySelector("#cloudDetail"),
  edgeDetail: document.querySelector("#edgeDetail"),
  reviewForm: document.querySelector("#reviewForm"),
  reviewConfidence: document.querySelector("#reviewConfidence"),
  retakeBtn: document.querySelector("#retakeBtn"),
  saveReviewBtn: document.querySelector("#saveReviewBtn"),
  toast: document.querySelector("#toast"),
};

function defaultApiBase() {
  const saved = localStorage.getItem("smartWardrobeApiBase");
  if (saved) return saved;
  if (location.protocol.startsWith("http")) return location.origin;
  return "http://192.168.137.2";
}

function apiUrl(path) {
  return `${state.apiBase}${path}`;
}

async function api(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...(options.headers || {}),
    },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function setStatus(ok, text) {
  els.status.textContent = text;
  els.status.classList.toggle("ok", ok);
  els.status.classList.toggle("bad", !ok);
}

function setBusy(button, busy, text) {
  state.busy = busy;
  button.disabled = busy;
  button.textContent = text;
}

function showToast(text) {
  els.toast.textContent = text;
  els.toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => els.toast.classList.remove("show"), 2400);
}

function activateView(name) {
  const viewId = `${name}View`;
  document.body.dataset.view = name;
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelector(`#${viewId}`)?.classList.add("active");
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === name || (name === "review" && item.dataset.view === "capture"));
  });
}

async function loadAll() {
  try {
    setStatus(false, "连接中");
    state.health = await api("/api/health");
    const clothes = await api("/api/clothes");
    state.clothes = clothes.items || [];
    const city = encodeURIComponent(els.city.value || "Chengdu");
    const occasion = encodeURIComponent(els.occasion.value || "school");
    state.recommendation = await api(`/api/recommendations?city=${city}&occasion=${occasion}`);
    render();
    setStatus(true, "在线");
  } catch (error) {
    setStatus(false, "离线");
    showToast(error.message);
  }
}

function render() {
  const weather = state.recommendation?.weather || {};
  const tempText = typeof weather.temperature_c === "number" ? `${weather.temperature_c.toFixed(1)}°C` : "--";
  els.temp.textContent = tempText;
  els.count.textContent = String(state.clothes.length);
  els.camera.textContent = state.health?.camera?.available ? "正常" : "异常";
  els.weatherLine.textContent = `${els.city.value || "Chengdu"} · ${sceneLabel(els.occasion.value)} · ${tempText}`;
  const cloud = state.health?.vision?.cloud;
  const cloudReady = Boolean(cloud?.configured);
  els.pipelineChip.textContent = cloudReady ? "云端主体 + 边缘识别" : "边缘识别";
  els.cloudStatus.textContent = cloudReady ? "云端主体" : "本地裁剪";
  renderRecommendations();
  renderWardrobe();
}

function renderRecommendations() {
  const recommendations = state.recommendation?.recommendations || [];
  if (!recommendations.length) {
    const missing = (state.recommendation?.missing_categories || []).map(categoryLabel).join("、") || "衣物";
    els.todayTitle.textContent = "还缺一些衣物";
    els.todaySummary.textContent = `建议补充：${missing}`;
    els.mirrorPanel.innerHTML = `<article class="empty-card">缺少 ${escapeHtml(missing)}</article>`;
    els.recommendList.innerHTML = "";
    return;
  }
  const first = recommendations[0];
  els.todayTitle.textContent = first.summary || "今日推荐";
  els.todaySummary.textContent = `推荐分 ${first.score}`;
  renderMirror(first);
  els.recommendList.innerHTML = recommendations
    .slice(0, 3)
    .map((rec, index) => {
      const items = (rec.items || [])
        .map(
          (item) => `
            <div class="outfit-tile">
              ${item.image_url ? `<img src="${imageUrl(item.image_url)}" alt="${escapeHtml(item.name)}" />` : ""}
              <strong>${escapeHtml(item.name)}</strong>
              <span>${escapeHtml(categoryLabel(item.category))} · ${escapeHtml(item.color || "")}</span>
            </div>
          `
        )
        .join("");
      const reasons = (rec.reason || []).map((text) => `<li>${escapeHtml(text)}</li>`).join("");
      return `
        <article class="recommend-card">
          <div class="section-head">
            <div>
              <p class="eyebrow">方案 ${index + 1}</p>
              <h3>${escapeHtml(rec.summary)}</h3>
            </div>
            <span class="score">${escapeHtml(rec.score)}</span>
          </div>
          <div class="outfit-row">${items}</div>
          <ul class="reason-list">${reasons}</ul>
        </article>
      `;
    })
    .join("");
}

function renderMirror(rec) {
  const slots = ["outer", "top", "bottom", "shoes"];
  const byCategory = new Map((rec.items || []).map((item) => [item.category, item]));
  els.mirrorPanel.innerHTML = `
    <article class="mirror-card">
      ${slots
        .map((slot) => {
          const item = byCategory.get(slot);
          if (!item) return `<div class="mirror-slot empty">${categoryLabel(slot)}</div>`;
          return `
            <div class="mirror-slot">
              ${item.image_url ? `<img src="${imageUrl(item.image_url)}" alt="${escapeHtml(item.name)}" />` : ""}
              <strong>${escapeHtml(item.name)}</strong>
              <span>${escapeHtml(item.color || "")}</span>
            </div>
          `;
        })
        .join("")}
    </article>
  `;
}

function renderWardrobe() {
  if (!state.clothes.length) {
    els.wardrobeGrid.innerHTML = `<article class="empty-card">暂无衣物</article>`;
    return;
  }
  els.wardrobeGrid.innerHTML = state.clothes
    .map(
      (item) => `
        <article class="clothes-card">
          ${item.image_url ? `<img src="${imageUrl(item.image_url)}" alt="${escapeHtml(item.name)}" />` : ""}
          <div class="clothes-body">
            <strong>${escapeHtml(item.name)}</strong>
            <div class="tag-row">
              <span>${escapeHtml(categoryLabel(item.category))}</span>
              <span>${escapeHtml(item.color || "未标色")}</span>
              <span>${escapeHtml(item.material || "未标材质")}</span>
            </div>
            ${renderAnalysis(item)}
            <button class="delete-btn" data-delete="${item.id}" type="button">删除</button>
          </div>
        </article>
      `
    )
    .join("");
}

function renderAnalysis(item) {
  const cloud = item.ai_analysis?.cloud_preprocess;
  const model = item.ai_analysis?.features?.model_match;
  const bits = [];
  if (cloud?.used) bits.push("云端裁剪");
  if (model?.name) bits.push(`模型：${model.name}`);
  if (item.ai_analysis?.review?.confirmed) bits.push("已审核");
  if (!bits.length) return "";
  return `<p class="analysis-note">${bits.map(escapeHtml).join(" · ")}</p>`;
}

async function analyzeCapture() {
  if (state.busy) return;
  setBusy(els.analyzeCaptureBtn, true, "处理中");
  try {
    const result = await api("/api/clothes/capture/analyze", {
      method: "POST",
      body: JSON.stringify({
        category: "auto",
        season: "summer_light,spring_autumn",
        occasion: `${els.occasion.value || "school"},casual`,
        favorite_score: 4,
        use_viewfinder: true,
        use_cloud_preprocess: true,
      }),
    });
    state.pendingAnalysis = result.analysis || {};
    state.pendingCapture = result.capture || {};
    state.pendingDraft = normalizeDraft(result.draft || {});
    fillReviewForm();
    activateView("review");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(els.analyzeCaptureBtn, false, "拍照识别");
  }
}

function normalizeDraft(draft) {
  const category = draft.category || "top";
  return {
    ...draft,
    category,
    name: draft.name || state.pendingAnalysis?.item_name || DEFAULT_NAMES[category] || "新衣物",
    color: draft.color || "",
    material: draft.material || "cotton",
    warmth: draft.warmth || 3,
    favorite_score: draft.favorite_score || 4,
    season: draft.season || "summer_light,spring_autumn",
    occasion: draft.occasion || `${els.occasion.value || "school"},casual`,
  };
}

function fillReviewForm() {
  const draft = state.pendingDraft || {};
  const analysis = state.pendingAnalysis || {};
  const capture = state.pendingCapture || {};
  const cloud = capture.cloud_preprocess || {};
  els.reviewTitle.textContent = draft.name || "确认这件衣物";
  els.reviewImage.src = imageUrl(capture.image_url || draft.image_url || "");
  els.reviewBadge.textContent = Number(analysis?.confidence?.category || 0) >= 0.8 ? "高置信" : "待确认";
  els.cloudDetail.textContent = cloud.used ? `已裁剪 ${percent(cloud.confidence)}` : "回退本地";
  const match = analysis?.features?.model_match;
  els.edgeDetail.textContent = match?.name ? `${match.name} ${percent(match.score)}` : categoryLabel(draft.category);
  for (const [key, value] of Object.entries(draft)) {
    const input = els.reviewForm.elements[key];
    if (input) input.value = value ?? "";
  }
  els.reviewConfidence.innerHTML = `
    <span>类别 ${percent(analysis?.confidence?.category)}</span>
    <span>颜色 ${percent(analysis?.confidence?.color)}</span>
    <span>材质 ${percent(analysis?.confidence?.material)}</span>
  `;
}

async function saveReviewedItem(event) {
  event.preventDefault();
  if (!state.pendingDraft || state.busy) return;
  setBusy(els.saveReviewBtn, true, "入库中");
  try {
    const form = Object.fromEntries(new FormData(els.reviewForm).entries());
    const payload = {
      ...state.pendingDraft,
      ...form,
      warmth: Number(form.warmth || state.pendingDraft.warmth || 3),
      favorite_score: Number(form.favorite_score || state.pendingDraft.favorite_score || 4),
      category_confidence: 1,
      color_confidence: 1,
      material_confidence: 1,
      ai_analysis: {
        ...(state.pendingAnalysis || {}),
        cloud_preprocess: state.pendingCapture?.cloud_preprocess || {},
        capture: state.pendingCapture || {},
        review: {
          confirmed: true,
          confirmed_at: new Date().toISOString(),
        },
      },
      note: "云边协同入库，人工审核确认",
    };
    await api("/api/clothes", { method: "POST", body: JSON.stringify(payload) });
    state.pendingDraft = null;
    state.pendingAnalysis = null;
    state.pendingCapture = null;
    showToast("已入库");
    await loadAll();
    activateView("today");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(els.saveReviewBtn, false, "确认入库");
  }
}

function categoryLabel(category) {
  return CATEGORY_LABELS[category] || category || "";
}

function sceneLabel(scene) {
  return {
    school: "上课",
    commute: "通勤",
    casual: "休闲",
    sport: "运动",
    formal: "正式",
    date: "约会",
  }[scene] || scene;
}

function percent(value) {
  const n = Math.round(Number(value || 0) * 100);
  return n ? `${n}%` : "--";
}

function imageUrl(url) {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) return url;
  return `${state.apiBase}${url}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.view));
});

els.refresh.addEventListener("click", loadAll);
els.closetRefresh.addEventListener("click", loadAll);
els.city.addEventListener("change", () => {
  localStorage.setItem("smartWardrobeCity", els.city.value);
  loadAll();
});
els.occasion.addEventListener("change", loadAll);
els.analyzeCaptureBtn.addEventListener("click", analyzeCapture);
els.reviewForm.addEventListener("submit", saveReviewedItem);
els.retakeBtn.addEventListener("click", () => activateView("capture"));
els.wardrobeGrid.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete]");
  if (!button) return;
  try {
    await api(`/api/clothes/${button.dataset.delete}`, { method: "DELETE" });
    showToast("已删除");
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
});

const savedCity = localStorage.getItem("smartWardrobeCity");
if (savedCity) els.city.value = savedCity;
if (els.cameraStream && location.protocol.startsWith("http")) {
  els.cameraStream.src = apiUrl("/api/camera/stream");
}
loadAll();
