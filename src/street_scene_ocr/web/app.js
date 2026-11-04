// Upload page: pick a photo, run one or more engines, draw their boxes on top of the photo.
// Boxes are drawn in the browser from the JSON answer, so moving the threshold slider recolours
// them instantly; the "Annotated PNG" button asks the server for the same picture as a file.

const $ = (selector, root = document) => root.querySelector(selector);
const SVG_NS = "http://www.w3.org/2000/svg";

const state = {
  file: null,
  config: null,
  results: new Map(), // engine name -> API response
  threshold: 0.3,
  showUnsure: true,
};

const form = $("#form");
const fileInput = $("#file");
const dropzone = $("#dropzone");
const preview = $("#preview");
const runButton = $("#run");
const statusLine = $("#status");
const thresholdInput = $("#threshold");
const thresholdValue = $("#threshold-value");
const showUnsureInput = $("#show-unsure");
const traditionalInput = $("#to-traditional");
const results = $("#results");

function setStatus(message, isError = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", isError);
}

function selectedEngines() {
  return [...document.querySelectorAll("input[name=engine]:checked")].map((input) => input.value);
}

function updateRunButton() {
  runButton.disabled = !state.file || selectedEngines().length === 0;
}

function pickFile(file) {
  const allowed = state.config?.allowed_extensions ?? ["png", "jpg", "jpeg"];
  const extension = file.name.split(".").pop().toLowerCase();
  if (!allowed.includes(extension)) {
    setStatus(`Allowed image types are -> ${allowed.join(", ")}`, true);
    return;
  }
  const limit = (state.config?.max_upload_mb ?? 16) * 1024 * 1024;
  if (file.size > limit) {
    setStatus(`The image is larger than ${state.config?.max_upload_mb ?? 16} MB`, true);
    return;
  }
  state.file = file;
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;
  dropzone.classList.add("has-image");
  document.querySelectorAll(".sample").forEach((b) => b.classList.toggle("selected", b.dataset.name === file.name));
  setStatus(`${file.name} · ${(file.size / 1024).toFixed(0)} KB`);
  updateRunButton();
}

async function loadSample(sample) {
  const response = await fetch(`/static/samples/${sample.file}`);
  const blob = await response.blob();
  pickFile(new File([blob], sample.file, { type: blob.type }));
}

async function loadSamples() {
  const response = await fetch("/static/samples/index.json");
  if (!response.ok) return;
  const samples = await response.json();
  const strip = $("#samples");
  for (const sample of samples) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sample";
    button.dataset.name = sample.file;
    button.title = `${sample.title} (${sample.credit})`;
    button.innerHTML = `<img src="/static/samples/${sample.file}" alt="${sample.title}" loading="lazy">`;
    button.addEventListener("click", () => loadSample(sample));
    strip.append(button);
  }
}

async function loadEngines() {
  const response = await fetch("/api/engines");
  state.config = await response.json();
  state.threshold = state.config.default_min_confidence;
  thresholdInput.value = Math.round(state.threshold * 100);
  thresholdValue.textContent = `${thresholdInput.value}%`;
  traditionalInput.checked = state.config.default_to_traditional;
  $("#limits").textContent = `${state.config.allowed_extensions.join(", ")} · up to ${state.config.max_upload_mb} MB`;

  const list = $("#engines");
  list.replaceChildren();
  for (const engine of state.config.engines) {
    const label = document.createElement("label");
    label.className = "engine" + (engine.installed ? "" : " unavailable");
    label.title = engine.installed ? engine.homepage : `Not installed here (missing ${engine.missing.join(", ")})`;
    label.innerHTML = `
      <input type="checkbox" name="engine" value="${engine.name}">
      <span class="engine-title"></span>
      <span class="engine-summary"></span>`;
    $(".engine-title", label).textContent = engine.title + (engine.installed ? "" : " · not installed");
    $(".engine-summary", label).textContent = engine.summary;
    const box = $("input", label);
    box.disabled = !engine.installed;
    box.checked = engine.installed && engine.name === state.config.default_engine;
    box.addEventListener("change", updateRunButton);
    list.append(label);
  }
  if (!state.config.engines.length) list.innerHTML = `<p class="muted">No engine is enabled on this server.</p>`;
  updateRunButton();
}

function badge(text, strong = false) {
  const span = document.createElement("span");
  span.className = "badge" + (strong ? " strong" : "");
  span.textContent = text;
  return span;
}

function createCard(engineName) {
  const engine = state.config.engines.find((e) => e.name === engineName);
  const card = $("#card-template").content.firstElementChild.cloneNode(true);
  card.dataset.engine = engineName;
  $(".card-title", card).textContent = engine.title;
  card.title = engine.summary;
  $(".stage-image", card).src = preview.src;
  $(".spinner", card).hidden = false;
  return card;
}

function isConfident(region) {
  return region.confidence > state.threshold; // same rule as the server
}

function linkHover(polygon, item) {
  const on = () => { polygon.classList.add("active"); item.classList.add("active"); };
  const off = () => { polygon.classList.remove("active"); item.classList.remove("active"); };
  for (const el of [polygon, item]) {
    el.addEventListener("mouseenter", on);
    el.addEventListener("mouseleave", off);
  }
}

function renderResult(card, data) {
  $(".spinner", card).hidden = true;
  const badges = $(".badges", card);
  badges.replaceChildren(badge(`${(data.total_ms / 1000).toFixed(2)} s`, true));
  for (const [stage, ms] of Object.entries(data.stages_ms)) badges.append(badge(`${stage} ${Math.round(ms)} ms`));
  badges.append(badge(data.device), badge(`served by ${data.served_by}`));
  if (data.to_traditional) badges.append(badge("→ Traditional"));

  const svg = $(".overlay", card);
  svg.setAttribute("viewBox", `0 0 ${data.width} ${data.height}`);
  svg.replaceChildren();
  const list = $(".regions", card);
  list.replaceChildren();

  data.regions.forEach((region, index) => {
    const polygon = document.createElementNS(SVG_NS, "polygon");
    polygon.setAttribute("points", region.polygon.map(([x, y]) => `${x},${y}`).join(" "));
    polygon.dataset.index = index;
    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = `${region.text} ${(region.confidence * 100).toFixed(2)}%`;
    polygon.append(title);
    svg.append(polygon);

    const item = document.createElement("li");
    item.className = "region";
    item.innerHTML = `<span class="region-text"></span><span class="region-score"></span><span class="bar"><i></i></span>`;
    $(".region-text", item).textContent = region.text || "(empty)";
    $(".region-score", item).textContent = `${(region.confidence * 100).toFixed(2)}%`;
    $(".bar i", item).style.width = `${Math.max(2, region.confidence * 100)}%`;
    list.append(item);
    linkHover(polygon, item);
  });
  if (!data.regions.length) list.innerHTML = `<li class="region"><span class="muted">No text found.</span></li>`;
  applyThreshold(card, data);

  const copy = $(".copy", card);
  copy.disabled = false;
  copy.onclick = async () => {
    const text = data.regions.filter(isConfident).map((r) => r.text).join("\n");
    await navigator.clipboard.writeText(text);
    copy.textContent = "Copied";
    setTimeout(() => (copy.textContent = "Copy text"), 1200);
  };
  const download = $(".download", card);
  download.disabled = false;
  download.onclick = () => downloadAnnotated(data.engine, download);
}

function applyThreshold(card, data) {
  const polygons = card.querySelectorAll(".overlay polygon");
  const items = card.querySelectorAll(".regions .region");
  data.regions.forEach((region, index) => {
    const confident = isConfident(region);
    const hidden = !confident && !state.showUnsure;
    polygons[index]?.setAttribute("class", `${confident ? "ok" : "unsure"}${hidden ? " hidden" : ""}`);
    items[index]?.classList.toggle("unsure", !confident);
    items[index]?.classList.toggle("hidden", hidden);
  });
}

function refreshAll() {
  for (const card of results.querySelectorAll(".card")) {
    const data = state.results.get(card.dataset.engine);
    if (data) applyThreshold(card, data);
  }
}

function formData(engine) {
  const data = new FormData();
  data.append("file", state.file);
  data.append("engine", engine);
  data.append("min_confidence", String(state.threshold));
  data.append("to_traditional", String(traditionalInput.checked));
  return data;
}

async function errorMessage(response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

async function downloadAnnotated(engine, button) {
  button.disabled = true;
  button.textContent = "Drawing…";
  try {
    const data = formData(engine);
    data.append("show_unsure", String(state.showUnsure));
    const response = await fetch("/api/ocr/annotated", { method: "POST", body: data });
    if (!response.ok) throw new Error(await errorMessage(response));
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `${state.file.name.replace(/\.[^.]+$/, "")}-${engine}.png`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  } catch (error) {
    setStatus(`Could not draw the image: ${error.message}`, true);
  } finally {
    button.disabled = false;
    button.textContent = "Annotated PNG";
  }
}

async function runEngine(engine, card) {
  try {
    const response = await fetch("/api/ocr", { method: "POST", body: formData(engine) });
    if (!response.ok) throw new Error(await errorMessage(response));
    const data = await response.json();
    state.results.set(engine, data);
    renderResult(card, data);
  } catch (error) {
    $(".spinner", card).hidden = true;
    const message = $(".card-error", card);
    message.textContent = error.message;
    message.hidden = false;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const engines = selectedEngines();
  if (!state.file || !engines.length) return;
  runButton.disabled = true;
  state.results.clear();
  results.replaceChildren();
  const cards = engines.map((engine) => {
    const card = createCard(engine);
    results.append(card);
    return [engine, card];
  });
  setStatus(`Reading with ${engines.length} engine${engines.length > 1 ? "s" : ""}… the first run of an engine also loads its models.`);
  const started = performance.now();
  // One engine at a time: engines running side by side would share the CPU and every timing would be off.
  for (const [engine, card] of cards) await runEngine(engine, card);
  setStatus(`Done in ${((performance.now() - started) / 1000).toFixed(1)} s`);
  updateRunButton();
});

fileInput.addEventListener("change", () => fileInput.files[0] && pickFile(fileInput.files[0]));
for (const type of ["dragenter", "dragover"]) {
  dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzone.classList.add("dragging"); });
}
for (const type of ["dragleave", "drop"]) {
  dropzone.addEventListener(type, () => dropzone.classList.remove("dragging"));
}
dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  const file = event.dataTransfer.files[0];
  if (file) pickFile(file);
});
thresholdInput.addEventListener("input", () => {
  state.threshold = Number(thresholdInput.value) / 100;
  thresholdValue.textContent = `${thresholdInput.value}%`;
  refreshAll();
});
showUnsureInput.addEventListener("change", () => {
  state.showUnsure = showUnsureInput.checked;
  refreshAll();
});

loadEngines().catch((error) => setStatus(`Could not reach the server: ${error.message}`, true));
loadSamples();
