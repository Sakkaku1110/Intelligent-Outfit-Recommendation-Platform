const CATEGORY_LABELS = {
  top: "上衣",
  bottom: "裤子",
  outer: "外套",
  shoes: "鞋子",
  accessory: "配饰",
  auto: "自动",
};

const CATEGORY_DEFAULT_NAMES = {
  top: "新上衣",
  bottom: "新裤子",
  outer: "新外套",
  shoes: "新鞋子",
  accessory: "新配饰",
};

const state = {
  health: null,
  clothes: [],
  recommendation: null,
  pendingDraft: null,
  pendingAnalysis: null,
  pendingCapture: null,
  apiBase: defaultApiBase(),
  busy: false,
};

const els = {
  status: document.querySelector("#statusPill"),
  temp: document.querySelector("#tempMetric"),
  count: document.querySelector("#countMetric"),
  camera: document.querySelector("#cameraMetric"),
  city: document.querySelector("#cityInput"),
  occasion: document.querySelector("#occasionSelect"),
  refresh: document.querySelector("#refreshBtn"),
  quickRefresh: document.querySelector("#quickRefreshBtn"),
  quickWeather: document.querySelector("#quickWeatherText"),
  recommendList: document.querySelector("#recommendList"),
  mirrorPanel: document.querySelector("#mirrorPanel"),
  wardrobeGrid: document.querySelector("#wardrobeGrid"),
  analyzeCaptureBtn: document.querySelector("#analyzeCaptureBtn"),
  reviewForm: document.querySelector("#reviewForm"),
  reviewImage: document.querySelector("#reviewImage"),
  reviewBadge: document.querySelector("#reviewBadge"),
  reviewConfidence: document.querySelector("#reviewConfidence"),
  retakeBtn: document.querySelector("#retakeBtn"),
  saveReviewBtn: document.querySelector("#saveReviewBtn"),
  cameraStream: document.querySelector("#cameraStream"),
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

function setBusy(button, busy, text) {
  state.busy = busy;
  button.disabled = busy;
  button.textContent = text;
}

function setStatus(ok, text) {
  els.status.textContent = text;
  els.status.classList.toggle("ok", ok);
  els.status.classList.toggle("bad", !ok);
}

function showToast(text) {
  els.toast.textContent = text;
  els.toast.classList.add("show");
  setTimeout(() => els.toast.classList.remove("show"), 2200);
}

function activateView(viewId) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelector(`#${viewId}`).classList.add("active");
  document.querySelectorAll(".tab").forEach((tab) => {
    const isActive = tab.dataset.view === viewId || (viewId === "reviewView" && tab.dataset.view === "captureView");
    tab.classList.toggle("active", isActive);
  });
  document.body.classList.remove("capture-view", "review-view", "recommend-view", "wardrobe-view");
  document.body.classList.add(viewId.replace("View", "-view"));
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
  const tempText = weather.temperature_c === undefined ? "--" : `${weather.temperature_c.toFixed(1)}°C`;
  els.temp.textContent = tempText;
  els.count.textContent = String(state.clothes.length);
  els.camera.textContent = state.health?.camera?.available ? "正常" : "未检测";
  els.quickWeather.textContent = `${els.city.value || "Chengdu"} · ${sceneLabel(els.occasion.value)} · ${tempText}`;
  renderRecommendations();
  renderWardrobe();
}

function renderRecommendations() {
  const result = state.recommendation;
  if (!result || !result.recommendations?.length) {
    const missing = result?.missing_categories?.join("、") || "衣物";
    els.mirrorPanel.innerHTML = `<div class="mirror-empty">缺少${escapeHtml(missing)}</div>`;
    els.recommendList.innerHTML = `<div class="empty">缺少${escapeHtml(missing)}</div>`;
    return;
  }
  renderMirror(result.recommendations[0]);
  els.recommendList.innerHTML = result.recommendations
    .map((rec, index) => {
      const items = rec.items
        .map(
          (item) => `
            <div class="mini-item">
              ${item.image_url ? `<img src="${imageUrl(item.image_url)}" alt="${escapeHtml(item.name)}" />` : ""}
              <strong>${escapeHtml(item.name)}</strong>
              <span class="tag">${escapeHtml(item.category_label || item.category)}</span>
              <span class="tag">${escapeHtml(item.color || "未标色")}</span>
            </div>
          `
        )
        .join("");
      const reasons = (rec.reason || []).map((text) => `<li>${escapeHtml(text)}</li>`).join("");
      return `
        <article class="recommend-card">
          <div class="recommend-head">
            <div>
              <strong>推荐 ${index + 1}</strong>
              <p class="eyebrow">${escapeHtml(rec.summary)}</p>
            </div>
            <span class="score">${escapeHtml(rec.score)}</span>
          </div>
          <div class="outfit-items">${items}</div>
          <ul class="reason-list">${reasons}</ul>
        </article>
      `;
    })
    .join("");
}

function renderMirror(rec) {
  const items = rec.items || [];
  const slots = ["top", "outer", "bottom", "shoes"];
  const byCategory = new Map(items.map((item) => [item.category, item]));
  const slotHtml = slots
    .map((slot) => {
      const item = byCategory.get(slot);
      if (!item) return `<div class="mirror-slot empty-slot">${slotLabel(slot)}</div>`;
      const image = item.image_url
        ? `<img src="${imageUrl(item.image_url)}" alt="${escapeHtml(item.name)}" />`
        : `<div class="mirror-placeholder">${escapeHtml((item.category_label || "?").slice(0, 1))}</div>`;
      return `
        <div class="mirror-slot">
          ${image}
          <strong>${escapeHtml(item.name)}</strong>
          <span>${escapeHtml(item.color || "")} ${escapeHtml(item.material || "")}</span>
        </div>
      `;
    })
    .join("");
  els.mirrorPanel.innerHTML = `
    <article class="mirror-card">
      <div class="mirror-copy">
        <p class="label">今日试衣镜</p>
        <h2>${escapeHtml(rec.summary)}</h2>
        <p class="score">推荐分 ${escapeHtml(rec.score)}</p>
      </div>
      <div class="mirror-stack">${slotHtml}</div>
    </article>
  `;
}

function renderWardrobe() {
  if (!state.clothes.length) {
    els.wardrobeGrid.innerHTML = `<div class="empty">暂无衣物</div>`;
    return;
  }
  els.wardrobeGrid.innerHTML = state.clothes
    .map((item) => {
      const image = item.image_url
        ? `<img class="clothes-image" src="${imageUrl(item.image_url)}" alt="${escapeHtml(item.name)}" />`
        : `<div class="placeholder">${escapeHtml((item.category_label || "?").slice(0, 1))}</div>`;
      return `
        <article class="clothes-card">
          ${image}
          <div class="clothes-body">
            <strong>${escapeHtml(item.name)}</strong>
            <div class="tag-row">
              <span class="tag">${escapeHtml(item.category_label || item.category)}</span>
              <span class="tag">${escapeHtml(item.color || "未标色")}</span>
              <span class="tag">${escapeHtml(item.material || "未标材质")}</span>
              <span class="tag">保暖 ${escapeHtml(item.warmth)}</span>
              ${isReviewed(item) ? `<span class="tag reviewed-tag">已审核</span>` : ""}
            </div>
            ${renderConfidence(item)}
            <button class="danger-btn" data-delete="${item.id}" type="button">删除</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderConfidence(item) {
  if (isReviewed(item)) {
    const ai = item.ai_analysis || {};
    const confidence = ai.confidence || {};
    return `
      <div class="confidence-row">
        <span>AI原始：类 ${percent(confidence.category)} 色 ${percent(confidence.color)} 材 ${percent(confidence.material)}</span>
      </div>
    `;
  }
  const c1 = Math.round(Number(item.category_confidence || 0) * 100);
  const c2 = Math.round(Number(item.color_confidence || 0) * 100);
  const c3 = Math.round(Number(item.material_confidence || 0) * 100);
  if (!c1 && !c2 && !c3) return "";
  return `
    <div class="confidence-row">
      <span>类 ${c1}%</span>
      <span>色 ${c2}%</span>
      <span>材 ${c3}%</span>
    </div>
  `;
}

async function analyzeCapture() {
  if (state.busy) return;
  setBusy(els.analyzeCaptureBtn, true, "识别中");
  try {
    const analyzed = await api("/api/clothes/capture/analyze", {
      method: "POST",
      body: JSON.stringify({
        category: "auto",
        season: "summer_light,spring_autumn",
        occasion: `${els.occasion.value || "school"},casual`,
        favorite_score: 4,
        auto_analyze: true,
        use_viewfinder: true,
      }),
    });
    state.pendingDraft = normalizeDraft(analyzed.draft || {});
    state.pendingAnalysis = analyzed.analysis || {};
    state.pendingCapture = analyzed.capture || {};
    fillReviewForm();
    activateView("reviewView");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(els.analyzeCaptureBtn, false, "确认识别");
  }
}

function normalizeDraft(draft) {
  const category = draft.category || "top";
  return {
    ...draft,
    category,
    name: draft.name || CATEGORY_DEFAULT_NAMES[category] || "新衣物",
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
  els.reviewImage.src = imageUrl(capture.image_url || draft.image_url || "");
  for (const [key, value] of Object.entries(draft)) {
    const input = els.reviewForm.elements[key];
    if (input) input.value = value ?? "";
  }
  const categoryConfidence = Number(analysis?.confidence?.category || 0);
  els.reviewBadge.textContent = categoryConfidence < 0.55 ? "需要审核" : "已识别";
  els.reviewConfidence.innerHTML = `
    <div class="analysis-line">
      <span class="tag">类别 ${escapeHtml(categoryLabel(draft.category))} ${percent(categoryConfidence)}</span>
      <span class="tag">颜色 ${escapeHtml(draft.color || "未识别")} ${percent(analysis?.confidence?.color)}</span>
      <span class="tag">材质 ${escapeHtml(materialLabel(draft.material, analysis))} ${percent(analysis?.confidence?.material)}</span>
    </div>
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
        review: {
          confirmed: true,
          confirmed_at: new Date().toISOString(),
          original_category: state.pendingAnalysis?.category,
          original_color: state.pendingAnalysis?.color,
          original_material: state.pendingAnalysis?.material,
        },
      },
      note: "人工审核确认",
    };
    await api("/api/clothes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.pendingDraft = null;
    state.pendingAnalysis = null;
    state.pendingCapture = null;
    showToast("已入库");
    await loadAll();
    activateView("recommendView");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(els.saveReviewBtn, false, "确认入库");
  }
}

function isReviewed(item) {
  return Boolean(item?.ai_analysis?.review?.confirmed);
}

function categoryLabel(category) {
  return CATEGORY_LABELS[category] || category || "";
}

function slotLabel(slot) {
  return { top: "上衣", outer: "外套", bottom: "裤子", shoes: "鞋子" }[slot] || slot;
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

function materialLabel(material, analysis) {
  if (analysis?.material_label) return analysis.material_label;
  return material || "未识别";
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

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.view));
});

els.refresh.addEventListener("click", loadAll);
els.quickRefresh.addEventListener("click", loadAll);
els.city.addEventListener("change", () => {
  localStorage.setItem("smartWardrobeCity", els.city.value);
  loadAll();
});
els.occasion.addEventListener("change", loadAll);
els.analyzeCaptureBtn.addEventListener("click", analyzeCapture);
els.reviewForm.addEventListener("submit", saveReviewedItem);
els.retakeBtn.addEventListener("click", () => activateView("captureView"));

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
