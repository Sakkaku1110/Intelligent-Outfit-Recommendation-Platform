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
  pendingTiming: null,
  editingItem: null,
  closetSearch: "",
  closetCategory: "all",
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
  manualAdd: document.querySelector("#manualAddBtn"),
  closetSearch: document.querySelector("#closetSearchInput"),
  closetCategory: document.querySelector("#closetCategoryFilter"),
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
  reviewTaobaoLink: document.querySelector("#reviewTaobaoLink"),
  reviewMerchantImage: document.querySelector("#reviewMerchantImage"),
  reviewTaobaoBtn: document.querySelector("#reviewTaobaoBtn"),
  reviewTaobaoStatus: document.querySelector("#reviewTaobaoStatus"),
  retakeBtn: document.querySelector("#retakeBtn"),
  saveReviewBtn: document.querySelector("#saveReviewBtn"),
  itemEditor: document.querySelector("#itemEditor"),
  editorTitle: document.querySelector("#editorTitle"),
  editorPreview: document.querySelector("#editorPreview"),
  itemEditForm: document.querySelector("#itemEditForm"),
  editorTaobaoLink: document.querySelector("#editorTaobaoLink"),
  editorMerchantImage: document.querySelector("#editorMerchantImage"),
  editorTaobaoBtn: document.querySelector("#editorTaobaoBtn"),
  editorTaobaoStatus: document.querySelector("#editorTaobaoStatus"),
  closeEditor: document.querySelector("#closeEditorBtn"),
  deleteEdit: document.querySelector("#deleteEditBtn"),
  saveEdit: document.querySelector("#saveEditBtn"),
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
    item.classList.toggle(
      "active",
      item.dataset.view === name || (name === "review" && item.dataset.view === "capture")
    );
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
  els.pipelineChip.textContent = cloudReady ? `云端限时 ${cloud.timeout_sec || 4.2}s` : "边缘识别";
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
    els.mirrorPanel.innerHTML = `<div class="empty-card">缺少 ${escapeHtml(missing)}</div>`;
    els.recommendList.innerHTML = "";
    return;
  }
  const first = recommendations[0];
  els.todayTitle.textContent = "今日搭配";
  els.todaySummary.textContent = first.summary || `推荐分 ${first.score}`;
  renderOutfitBoard(first);
  els.recommendList.innerHTML = recommendations
    .slice(1, 3)
    .map((rec, index) => {
      const items = (rec.items || []).map(renderOutfitCard).join("");
      const reasons = (rec.reason || []).slice(0, 3).map((text) => `<li>${escapeHtml(text)}</li>`).join("");
      return `
        <section class="recommend-card">
          <div class="section-head">
            <div>
              <p class="eyebrow">备用方案 ${index + 2}</p>
              <h3>${escapeHtml(rec.summary || "搭配方案")}</h3>
            </div>
            <span class="score">${escapeHtml(rec.score)}</span>
          </div>
          <div class="outfit-row">${items}</div>
          <ul class="reason-list">${reasons}</ul>
        </section>
      `;
    })
    .join("");
}

function renderOutfitBoard(rec) {
  const order = { top: 1, bottom: 2, shoes: 3, outer: 4, accessory: 5 };
  const items = [...(rec.items || [])].sort((a, b) => (order[a.category] || 9) - (order[b.category] || 9));
  els.mirrorPanel.innerHTML = `
    <section class="outfit-board">
      ${items.map(renderOutfitCard).join("")}
    </section>
  `;
}

function renderOutfitCard(item) {
  const url = displayImageUrl(item);
  return `
    <article class="outfit-card">
      <div class="outfit-image">
        ${url ? `<img src="${imageUrl(url)}" alt="${escapeHtml(item.name)}" />` : `<span>${escapeHtml(categoryLabel(item.category))}</span>`}
      </div>
      <strong>${escapeHtml(item.name)}</strong>
      <span>${escapeHtml(item.color || categoryLabel(item.category))}</span>
    </article>
  `;
}

function renderWardrobe() {
  const items = filteredClothes();
  if (!items.length) {
    els.wardrobeGrid.innerHTML = `<div class="empty-card">没有匹配的衣物</div>`;
    return;
  }
  els.wardrobeGrid.innerHTML = items.map(renderClothesCard).join("");
}

function filteredClothes() {
  const q = state.closetSearch.trim().toLowerCase();
  return state.clothes.filter((item) => {
    if (state.closetCategory !== "all" && item.category !== state.closetCategory) return false;
    if (!q) return true;
    return [item.name, item.color, item.material, item.note, categoryLabel(item.category)]
      .some((value) => String(value || "").toLowerCase().includes(q));
  });
}

function renderClothesCard(item) {
  const cloud = item.ai_analysis?.cloud_preprocess;
  const timing = item.ai_analysis?.capture?.timing_ms || item.ai_analysis?.timing_ms;
  const url = displayImageUrl(item);
  return `
    <article class="clothes-card" data-edit="${item.id}">
      <div class="clothes-image">
        ${url ? `<img src="${imageUrl(url)}" alt="${escapeHtml(item.name)}" />` : `<span>${escapeHtml(categoryLabel(item.category))}</span>`}
      </div>
      <div class="clothes-body">
        <strong>${escapeHtml(item.name)}</strong>
        <span class="date-line">${escapeHtml(formatDate(item.created_at))}</span>
        <div class="tag-row">
          <span>${escapeHtml(categoryLabel(item.category))}</span>
          <span>${escapeHtml(item.color || "未标色")}</span>
          <span>${escapeHtml(item.material || "未标材质")}</span>
        </div>
        <p class="analysis-note">${cloud?.used ? "云端主体" : "本地识别"}${timing?.total_ms ? ` · ${(timing.total_ms / 1000).toFixed(1)}s` : ""}</p>
        <div class="card-actions">
          <button class="secondary-btn small-btn" data-action="edit" data-id="${item.id}" type="button">编辑</button>
          <button class="delete-btn small-btn" data-action="delete" data-id="${item.id}" type="button">删除</button>
        </div>
      </div>
    </article>
  `;
}

async function analyzeCapture() {
  if (state.busy) return;
  setBusy(els.analyzeCaptureBtn, true, "识别中");
  const started = performance.now();
  try {
    const result = await api("/api/clothes/capture/analyze", {
      method: "POST",
      body: JSON.stringify({
        category: "auto",
        season: "summer_light,spring_autumn",
        occasion: `${els.occasion.value || "school"},casual`,
        favorite_score: 4,
        resolution: "640x480",
        skip_frames: 2,
        use_viewfinder: true,
        use_cloud_preprocess: true,
      }),
    });
    state.pendingAnalysis = result.analysis || {};
    state.pendingCapture = result.capture || {};
    state.pendingTiming = result.timing_ms || state.pendingCapture.timing_ms || {};
    state.pendingDraft = normalizeDraft(result.draft || {});
    fillReviewForm();
    activateView("review");
    showToast(`识别完成 ${(performance.now() - started) / 1000 < 0.1 ? "" : `${((performance.now() - started) / 1000).toFixed(1)}s`}`);
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
    source_platform: draft.source_platform || "",
    source_url: draft.source_url || "",
    source_item_id: draft.source_item_id || "",
    source_title: draft.source_title || "",
    merchant_image_url: draft.merchant_image_url || "",
    merchant_image_path: draft.merchant_image_path || "",
    display_image_url: draft.display_image_url || "",
    display_image_path: draft.display_image_path || "",
  };
}

function fillReviewForm() {
  const draft = state.pendingDraft || {};
  const analysis = state.pendingAnalysis || {};
  const capture = state.pendingCapture || {};
  const cloud = capture.cloud_preprocess || {};
  const timing = state.pendingTiming || {};
  els.reviewTitle.textContent = draft.name || "确认这件衣物";
  els.reviewImage.src = imageUrl(displayImageUrl(draft) || capture.image_url || draft.image_url || "");
  els.reviewBadge.textContent = timing.total_ms ? `${(timing.total_ms / 1000).toFixed(1)}s` : "待确认";
  els.cloudDetail.textContent = cloud.used
    ? `已裁剪 ${percent(cloud.confidence)} · ${msText(timing.cloud_preprocess_ms || cloud.elapsed_ms)}`
    : `回退本地 · ${msText(timing.cloud_preprocess_ms || cloud.elapsed_ms)}`;
  const match = analysis?.features?.model_match;
  els.edgeDetail.textContent = match?.name
    ? `${match.name} ${percent(match.score)} · ${msText(timing.edge_analysis_ms)}`
    : `${categoryLabel(draft.category)} · ${msText(timing.edge_analysis_ms)}`;
  for (const [key, value] of Object.entries(draft)) {
    const input = els.reviewForm.elements[key];
    if (input) input.value = value ?? "";
  }
  if (els.reviewTaobaoStatus) {
    els.reviewTaobaoStatus.textContent = draft.display_image_url ? "已生成商家图展示卡" : "";
  }
  els.reviewConfidence.innerHTML = `
    <span>总耗时 ${msText(timing.total_ms)}</span>
    <span>类别 ${percent(analysis?.confidence?.category)}</span>
    <span>颜色 ${percent(analysis?.confidence?.color)}</span>
    <span>材质 ${percent(analysis?.confidence?.material)}</span>
  `;
}

async function importTaobaoForReview() {
  if (!state.pendingDraft || state.busy) return;
  const form = Object.fromEntries(new FormData(els.reviewForm).entries());
  const payload = {
    ...state.pendingDraft,
    ...form,
    source_url: els.reviewTaobaoLink?.value || form.source_url || "",
    merchant_image_url: els.reviewMerchantImage?.value || form.merchant_image_url || "",
  };
  if (!payload.source_url && !payload.merchant_image_url) {
    showToast("请先粘贴淘宝链接或商家图片链接");
    return;
  }
  setBusy(els.reviewTaobaoBtn, true, "处理中");
  if (els.reviewTaobaoStatus) {
    els.reviewTaobaoStatus.textContent = "正在解析淘宝链接并生成展示卡...";
  }
  try {
    const result = await api("/api/commerce/taobao/resolve", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.pendingDraft = normalizeDraft({
      ...state.pendingDraft,
      ...(result.patch || {}),
    });
    fillReviewForm();
    const message = result.ok ? "已导入淘宝商家图" : (result.message || "已解析链接，未自动拿到商品图");
    if (els.reviewTaobaoStatus) els.reviewTaobaoStatus.textContent = message;
    showToast(message);
  } catch (error) {
    if (els.reviewTaobaoStatus) els.reviewTaobaoStatus.textContent = error.message;
    showToast(error.message);
  } finally {
    setBusy(els.reviewTaobaoBtn, false, "导入展示图");
  }
}

async function saveReviewedItem(event) {
  event.preventDefault();
  if (!state.pendingDraft || state.busy) return;
  setBusy(els.saveReviewBtn, true, "入库中");
  const started = performance.now();
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
        capture: {
          ...(state.pendingCapture || {}),
          timing_ms: state.pendingTiming || {},
        },
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
    state.pendingTiming = null;
    showToast(`已入库 ${((performance.now() - started) / 1000).toFixed(1)}s`);
    await loadAll();
    activateView("wardrobe");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(els.saveReviewBtn, false, "确认入库");
  }
}

function openEditor(item) {
  const isNew = !item;
  state.editingItem = item || {
    name: "新衣物",
    category: "top",
    color: "",
    material: "cotton",
    warmth: 3,
    favorite_score: 3,
    season: "summer_light,spring_autumn",
    occasion: "school,casual",
    note: "",
    image_url: "",
    image_path: "",
    display_image_url: "",
    display_image_path: "",
    source_platform: "",
    source_url: "",
    source_item_id: "",
    source_title: "",
    merchant_image_url: "",
    merchant_image_path: "",
  };
  els.editorTitle.textContent = isNew ? "新增衣物" : "编辑衣物";
  fillEditorForm(state.editingItem);
  els.deleteEdit.hidden = isNew;
  els.itemEditor.hidden = false;
}

function closeEditor() {
  state.editingItem = null;
  els.itemEditor.hidden = true;
}

function fillEditorForm(item) {
  for (const input of els.itemEditForm.elements) {
    if (!input.name) continue;
    input.value = item[input.name] ?? "";
  }
  const url = displayImageUrl(item);
  els.editorPreview.src = url ? imageUrl(url) : "";
  els.editorPreview.hidden = !url;
  if (els.editorTaobaoStatus) {
    els.editorTaobaoStatus.textContent = item.display_image_url ? "已生成商家图展示卡" : "";
  }
}

async function importTaobaoForEditor() {
  if (!state.editingItem || state.busy) return;
  const form = Object.fromEntries(new FormData(els.itemEditForm).entries());
  const payload = {
    ...state.editingItem,
    ...form,
    source_url: els.editorTaobaoLink?.value || form.source_url || "",
    merchant_image_url: els.editorMerchantImage?.value || form.merchant_image_url || "",
  };
  if (!payload.source_url && !payload.merchant_image_url) {
    showToast("请先粘贴淘宝链接或商家图片链接");
    return;
  }
  setBusy(els.editorTaobaoBtn, true, "处理中");
  if (els.editorTaobaoStatus) {
    els.editorTaobaoStatus.textContent = "正在生成商家图展示卡...";
  }
  try {
    if (payload.id) {
      const result = await api(`/api/clothes/${payload.id}/taobao`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.editingItem = result.item || { ...state.editingItem, ...(result.patch || {}) };
      const index = state.clothes.findIndex((item) => Number(item.id) === Number(state.editingItem.id));
      if (index >= 0) state.clothes[index] = state.editingItem;
      fillEditorForm(state.editingItem);
      renderWardrobe();
      showToast(result.ok ? "已导入淘宝商家图" : (result.message || "已解析链接"));
    } else {
      const result = await api("/api/commerce/taobao/resolve", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.editingItem = { ...state.editingItem, ...(result.patch || {}) };
      fillEditorForm(state.editingItem);
      showToast(result.ok ? "已导入淘宝商家图" : (result.message || "已解析链接"));
    }
  } catch (error) {
    if (els.editorTaobaoStatus) els.editorTaobaoStatus.textContent = error.message;
    showToast(error.message);
  } finally {
    setBusy(els.editorTaobaoBtn, false, "导入展示图");
  }
}

async function saveEditorItem(event) {
  event.preventDefault();
  if (!state.editingItem || state.busy) return;
  setBusy(els.saveEdit, true, "保存中");
  try {
    const form = Object.fromEntries(new FormData(els.itemEditForm).entries());
    const payload = {
      ...state.editingItem,
      ...form,
      warmth: Number(form.warmth || 3),
      favorite_score: Number(form.favorite_score || 3),
    };
    if (payload.id) {
      await api(`/api/clothes/${payload.id}`, { method: "PUT", body: JSON.stringify(payload) });
      showToast("已更新");
    } else {
      await api("/api/clothes", { method: "POST", body: JSON.stringify(payload) });
      showToast("已新增");
    }
    closeEditor();
    await loadAll();
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(els.saveEdit, false, "保存");
  }
}

async function deleteItem(id) {
  if (!id || state.busy) return;
  try {
    await api(`/api/clothes/${id}`, { method: "DELETE" });
    showToast("已删除");
    if (state.editingItem?.id === Number(id)) closeEditor();
    await loadAll();
  } catch (error) {
    showToast(error.message);
  }
}

function findItem(id) {
  return state.clothes.find((item) => Number(item.id) === Number(id));
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

function msText(value) {
  const n = Number(value || 0);
  return n ? `${(n / 1000).toFixed(1)}s` : "--";
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function imageUrl(url) {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) return url;
  return `${state.apiBase}${url}`;
}

function displayImageUrl(item) {
  return item?.display_image_url || item?.merchant_image_url || item?.image_url || "";
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
els.manualAdd.addEventListener("click", () => openEditor(null));
els.city.addEventListener("change", () => {
  localStorage.setItem("smartWardrobeCity", els.city.value);
  loadAll();
});
els.occasion.addEventListener("change", loadAll);
els.closetSearch.addEventListener("input", () => {
  state.closetSearch = els.closetSearch.value;
  renderWardrobe();
});
els.closetCategory.addEventListener("change", () => {
  state.closetCategory = els.closetCategory.value;
  renderWardrobe();
});
els.analyzeCaptureBtn.addEventListener("click", analyzeCapture);
els.reviewTaobaoBtn?.addEventListener("click", importTaobaoForReview);
els.reviewForm.addEventListener("submit", saveReviewedItem);
els.retakeBtn.addEventListener("click", () => activateView("capture"));
els.editorTaobaoBtn?.addEventListener("click", importTaobaoForEditor);
els.itemEditForm.addEventListener("submit", saveEditorItem);
els.closeEditor.addEventListener("click", closeEditor);
els.deleteEdit.addEventListener("click", () => deleteItem(state.editingItem?.id));
els.itemEditor.addEventListener("click", (event) => {
  if (event.target === els.itemEditor) closeEditor();
});
els.wardrobeGrid.addEventListener("click", (event) => {
  const action = event.target.closest("[data-action]");
  if (action?.dataset.action === "delete") {
    event.stopPropagation();
    deleteItem(action.dataset.id);
    return;
  }
  if (action?.dataset.action === "edit") {
    event.stopPropagation();
    openEditor(findItem(action.dataset.id));
    return;
  }
  const card = event.target.closest("[data-edit]");
  if (card) openEditor(findItem(card.dataset.edit));
});

const savedCity = localStorage.getItem("smartWardrobeCity");
if (savedCity) els.city.value = savedCity;
if (els.cameraStream && location.protocol.startsWith("http")) {
  els.cameraStream.src = apiUrl("/api/camera/stream");
}
const initialView = new URLSearchParams(location.search).get("view");
if (["today", "capture", "wardrobe"].includes(initialView)) {
  activateView(initialView);
}
loadAll();
