import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

const NODE_TYPE = "SimpleImageCompare";
const DEFAULT_HEIGHT = 730;

function imageList(value) {
  return Array.isArray(value) ? value.filter((item) => item?.filename) : [];
}

function imageUrl(image, cacheKey) {
  const query = new URLSearchParams({
    filename: image.filename,
    subfolder: image.subfolder || "",
    type: image.type || "temp",
    rand: String(cacheKey),
  });
  const path = `/view?${query.toString()}`;
  return typeof api.apiURL === "function" ? api.apiURL(path) : path;
}

function stopCanvasEvent(event) {
  event.stopPropagation();
}

function makeElement(tag, className) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  return element;
}

function installCompareWidget(node) {
  if (!node || node.__xiawanCompareWidget) return node?.__xiawanCompareWidget;

  const root = makeElement("div", "xiawan-compare-preview");
  root.style.cssText = [
    "box-sizing:border-box",
    `height:${DEFAULT_HEIGHT}px`,
    "display:flex",
    "flex-direction:column",
    "gap:8px",
    "padding:6px 8px 8px",
    "background:#15191d",
    "border:1px solid rgba(255,255,255,.12)",
    "border-radius:4px",
    "color:#e6edf3",
    "font:12px sans-serif",
  ].join(";");

  const stage = makeElement("div", "xiawan-compare-stage");
  stage.style.cssText = [
    "position:relative",
    "flex:1 1 auto",
    "min-height:0",
    "overflow:hidden",
    "background:#0c0f12",
    "border-radius:3px",
  ].join(";");

  const imageB = makeElement("img", "xiawan-compare-image xiawan-compare-image-b");
  const imageA = makeElement("img", "xiawan-compare-image xiawan-compare-image-a");
  for (const image of [imageA, imageB]) {
    image.draggable = false;
    image.alt = "";
    image.style.cssText = [
      "position:absolute",
      "inset:0",
      "width:100%",
      "height:100%",
      "object-fit:contain",
      "user-select:none",
      "pointer-events:none",
    ].join(";");
  }
  imageB.style.zIndex = "1";
  imageA.style.zIndex = "2";

  const empty = makeElement("div", "xiawan-compare-empty");
  empty.textContent = "运行后显示对比预览";
  empty.style.cssText = [
    "position:absolute",
    "inset:0",
    "display:grid",
    "place-items:center",
    "color:#8b949e",
    "pointer-events:none",
  ].join(";");

  const divider = makeElement("div", "xiawan-compare-divider");
  divider.style.cssText = [
    "position:absolute",
    "top:0",
    "bottom:0",
    "left:50%",
    "z-index:3",
    "width:2px",
    "transform:translateX(-1px)",
    "background:#ffffff",
    "box-shadow:0 0 0 1px rgba(0,0,0,.35)",
    "pointer-events:none",
  ].join(";");

  const labelA = makeElement("span", "xiawan-compare-label xiawan-compare-label-a");
  const labelB = makeElement("span", "xiawan-compare-label xiawan-compare-label-b");
  labelA.textContent = "图像 A";
  labelB.textContent = "图像 B";
  for (const label of [labelA, labelB]) {
    label.style.cssText = [
      "position:absolute",
      "top:8px",
      "z-index:4",
      "padding:3px 6px",
      "border-radius:3px",
      "background:rgba(0,0,0,.58)",
      "color:#fff",
      "pointer-events:none",
    ].join(";");
  }
  labelA.style.left = "8px";
  labelB.style.right = "8px";

  stage.append(imageB, imageA, empty, divider, labelA, labelB);

  const controls = makeElement("div", "xiawan-compare-controls");
  controls.style.cssText = [
    "display:flex",
    "align-items:center",
    "gap:8px",
    "min-height:28px",
  ].join(";");

  const slider = makeElement("input", "xiawan-compare-slider");
  slider.type = "range";
  slider.min = "0";
  slider.max = "100";
  slider.value = "50";
  slider.title = "拖动滑块调整图像 A 的显示范围";
  slider.style.cssText = "flex:1 1 auto; min-width:0; accent-color:#58a6ff;";

  const sliderValue = makeElement("span", "xiawan-compare-slider-value");
  sliderValue.style.cssText = "min-width:34px; text-align:right; color:#8b949e;";

  const batchSelect = makeElement("select", "xiawan-compare-batch");
  batchSelect.title = "选择批次结果";
  batchSelect.style.cssText = "display:none; max-width:92px; background:#21262d; color:#e6edf3; border:1px solid #484f58; border-radius:3px;";

  controls.append(slider, sliderValue, batchSelect);
  root.append(stage, controls);

  const state = {
    aImages: [],
    bImages: [],
    index: 0,
    cacheKey: 0,
  };

  function setSlider(value) {
    const normalized = Math.max(0, Math.min(100, Number(value) || 0));
    slider.value = String(normalized);
    sliderValue.textContent = `${Math.round(normalized)}%`;
    divider.style.left = `${normalized}%`;
    imageA.style.clipPath = `inset(0 ${100 - normalized}% 0 0)`;
  }

  function updateBatchOptions() {
    const count = Math.max(state.aImages.length, state.bImages.length);
    batchSelect.replaceChildren();
    if (count <= 1) {
      batchSelect.style.display = "none";
      state.index = 0;
      return;
    }
    batchSelect.style.display = "block";
    for (let index = 0; index < count; index += 1) {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = `批次 ${index + 1}`;
      batchSelect.append(option);
    }
    state.index = Math.min(state.index, count - 1);
    batchSelect.value = String(state.index);
  }

  function renderPair() {
    const a = state.aImages[state.index];
    const b = state.bImages[state.index];
    const hasA = Boolean(a);
    const hasB = Boolean(b);
    imageA.style.display = hasA ? "block" : "none";
    imageB.style.display = hasB ? "block" : "none";
    labelA.style.display = hasA ? "block" : "none";
    labelB.style.display = hasB ? "block" : "none";
    divider.style.display = hasA && hasB ? "block" : "none";
    empty.style.display = hasA || hasB ? "none" : "grid";
    if (hasA) imageA.src = imageUrl(a, state.cacheKey);
    if (hasB) imageB.src = imageUrl(b, state.cacheKey);
    setSlider(slider.value);
  }

  function update(message) {
    state.aImages = imageList(message?.a_images);
    state.bImages = imageList(message?.b_images);
    state.index = 0;
    state.cacheKey = Date.now();
    updateBatchOptions();
    renderPair();

    // The standard payload is kept for older frontends; prevent it from
    // drawing a second preview below this dedicated DOM widget.
    node.imgs = [];
    node.imageIndex = 0;
    node.graph?.setDirtyCanvas?.(true, true);
  }

  function updateBase(images) {
    state.aImages = imageList(images);
    state.bImages = [];
    state.index = 0;
    state.cacheKey = Date.now();
    updateBatchOptions();
    renderPair();
    node.graph?.setDirtyCanvas?.(true, true);
  }

  slider.addEventListener("input", () => setSlider(slider.value));
  batchSelect.addEventListener("change", () => {
    state.index = Number(batchSelect.value) || 0;
    renderPair();
  });
  for (const element of [slider, batchSelect]) {
    element.addEventListener("mousedown", stopCanvasEvent);
    element.addEventListener("pointerdown", stopCanvasEvent);
    element.addEventListener("wheel", stopCanvasEvent);
  }

  const widget = node.addDOMWidget("xiawan_compare_preview", "div", root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => DEFAULT_HEIGHT,
  });
  widget.value = null;
  node.__xiawanCompareWidget = widget;
  node.__xiawanCompareUpdate = update;
  node.__xiawanCompareUpdateBase = updateBase;
  setSlider(50);
  return widget;
}

function updateBasePreviewNodes(images) {
  const nodes = app.graph?._nodes || [];
  for (const node of nodes) {
    if (node.type === NODE_TYPE) {
      installCompareWidget(node);
      node.__xiawanCompareUpdateBase?.(images);
    }
  }
}

app.registerExtension({
  name: "Xiawan.SimpleImageCompare",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE_TYPE) return;

    const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = originalOnNodeCreated?.apply(this, arguments);
      installCompareWidget(this);
      return result;
    };

    const originalOnConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = originalOnConfigure?.apply(this, arguments);
      installCompareWidget(this);
      return result;
    };

    const originalOnExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const result = originalOnExecuted?.apply(this, arguments);
      installCompareWidget(this);
      this.__xiawanCompareUpdate?.(message);
      return result;
    };
  },

  loadedGraphNode(node) {
    if (node?.type === NODE_TYPE) installCompareWidget(node);
  },

  setup() {
    if (api.__xiawanBasePreviewListener || typeof api.addEventListener !== "function") return;
    const listener = (event) => {
      const images = imageList(event?.detail?.output?.xiawan_base_images);
      if (images.length) updateBasePreviewNodes(images);
    };
    api.addEventListener("executed", listener);
    api.__xiawanBasePreviewListener = listener;
  },
});
