// Picture to ASCII — converts an uploaded image into ASCII art rendered on a canvas.

const $ = (id) => document.getElementById(id);

const FONT_FAMILY = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace';
const PADDING = 16;
const MAX_CANVAS_SIDE = 16000;
const MAX_CANVAS_AREA = 16_000_000; // stay under iOS Safari's ~16.7M px limit
const MAX_ROWS = 2000;

const els = {
  file: $("file"),
  dropzone: $("dropzone"),
  placeholder: $("placeholder"),
  output: $("output"),
  sampler: $("sampler"),
  charsetPreset: $("charsetPreset"),
  customWrap: $("customWrap"),
  customChars: $("customChars"),
  colorMode: $("colorMode"),
  solidWrap: $("solidWrap"),
  gradientWrap: $("gradientWrap"),
};

// Range inputs that display their current value in a sibling <output>.
const RANGES = ["cols", "fontSize", "lineHeight", "variance", "brightness", "contrast", "gamma"];

let image = null;
let lastText = "";

// ---------- settings ----------

function readSettings() {
  const preset = els.charsetPreset.value;
  // Split by code point so emoji and other astral characters stay intact.
  let charset = [...(preset === "custom" ? els.customChars.value : preset)];
  if (charset.length < 2) charset = [" ", "@"];

  return {
    cols: +$("cols").value,
    fontSize: +$("fontSize").value,
    lineHeight: +$("lineHeight").value,
    charset,
    variance: +$("variance").value,
    invert: $("invert").checked,
    brightness: +$("brightness").value / 100,
    contrast: +$("contrast").value / 100,
    gamma: +$("gamma").value,
    colorMode: els.colorMode.value,
    fgColor: hexToRgb($("fgColor").value),
    gradStart: hexToRgb($("gradStart").value),
    gradEnd: hexToRgb($("gradEnd").value),
    gradDir: $("gradDir").value,
    bgColor: $("bgColor").value,
  };
}

// ---------- helpers ----------

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const clamp01 = (v) => Math.min(1, Math.max(0, v));
const lerp = (a, b, t) => a + (b - a) * t;
const lerpRgb = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];

// Deterministic per-cell noise in [-1, 1], so variance doesn't flicker on every re-render.
function cellNoise(x, y) {
  let h = (x * 374761393 + y * 668265263) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return ((h >>> 0) / 4294967295) * 2 - 1;
}

function adjustTone(b, s) {
  const k = s.contrast >= 0 ? 1 + s.contrast * 3 : 1 + s.contrast;
  b = (b - 0.5) * k + 0.5 + s.brightness;
  b = Math.pow(clamp01(b), 1 / s.gamma);
  return s.invert ? 1 - b : b;
}

function gradientT(x, y, cols, rows, b, dir) {
  const u = cols > 1 ? x / (cols - 1) : 0;
  const v = rows > 1 ? y / (rows - 1) : 0;
  switch (dir) {
    case "vertical": return v;
    case "diagonal": return (u + v) / 2;
    case "radial": return clamp01(Math.hypot(u - 0.5, v - 0.5) / Math.SQRT1_2);
    case "brightness": return b;
    default: return u;
  }
}

// ---------- conversion ----------

function convert() {
  if (!image) return;
  const s = readSettings();

  // Measure the monospace cell so the output keeps the image's aspect ratio.
  const ctx = els.output.getContext("2d");
  const font = `${s.fontSize}px ${FONT_FAMILY}`;
  ctx.font = font;
  const cellW = ctx.measureText("M").width;
  const cellH = s.fontSize * s.lineHeight;

  const cols = s.cols;
  const rows = Math.min(MAX_ROWS, Math.max(1, Math.round((image.height / image.width) * cols * (cellW / cellH))));

  // Downsample the image to one pixel per character cell.
  const sampler = els.sampler;
  sampler.width = cols;
  sampler.height = rows;
  const sctx = sampler.getContext("2d", { willReadFrequently: true });
  sctx.clearRect(0, 0, cols, rows);
  sctx.drawImage(image, 0, 0, cols, rows);
  const px = sctx.getImageData(0, 0, cols, rows).data;

  const chars = s.charset;
  const last = chars.length - 1;
  const spread = s.variance * Math.max(1, last * 0.5);

  const grid = [];
  const lines = [];
  for (let y = 0; y < rows; y++) {
    let line = "";
    const row = [];
    for (let x = 0; x < cols; x++) {
      const i = (y * cols + x) * 4;
      const r = px[i], g = px[i + 1], bl = px[i + 2], a = px[i + 3] / 255;
      const lum = ((0.2126 * r + 0.7152 * g + 0.0722 * bl) / 255) * a;
      const b = adjustTone(lum, s);

      let idx = b * last;
      if (spread > 0) idx += cellNoise(x, y) * spread;
      idx = Math.round(Math.min(last, Math.max(0, idx)));

      const ch = chars[idx];
      line += ch;
      row.push({ ch, b, rgb: [r, g, bl] });
    }
    lines.push(line);
    grid.push(row);
  }
  lastText = lines.join("\n");

  render(grid, cols, rows, cellW, cellH, font, s);
}

function render(grid, cols, rows, cellW, cellH, font, s) {
  const canvas = els.output;
  const cssW = Math.ceil(cols * cellW + PADDING * 2);
  const cssH = Math.ceil(rows * cellH + PADDING * 2);
  const dpr = Math.min(
    window.devicePixelRatio || 1,
    2,
    MAX_CANVAS_SIDE / Math.max(cssW, cssH),
    Math.sqrt(MAX_CANVAS_AREA / (cssW * cssH))
  );

  canvas.width = Math.floor(cssW * dpr);
  canvas.height = Math.floor(cssH * dpr);
  canvas.style.width = cssW + "px";
  canvas.style.height = cssH + "px";

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = s.bgColor;
  ctx.fillRect(0, 0, cssW, cssH);
  ctx.font = font;
  ctx.textBaseline = "middle";

  if (s.colorMode === "solid") {
    ctx.fillStyle = `rgb(${s.fgColor.join(",")})`;
  }

  for (let y = 0; y < rows; y++) {
    const cy = PADDING + y * cellH + cellH / 2;
    for (let x = 0; x < cols; x++) {
      const cell = grid[y][x];
      if (cell.ch === " ") continue;

      if (s.colorMode === "original") {
        ctx.fillStyle = `rgb(${cell.rgb.join(",")})`;
      } else if (s.colorMode === "gradient") {
        const t = gradientT(x, y, cols, rows, cell.b, s.gradDir);
        const [r, g, b] = lerpRgb(s.gradStart, s.gradEnd, t);
        ctx.fillStyle = `rgb(${r | 0},${g | 0},${b | 0})`;
      }
      ctx.fillText(cell.ch, PADDING + x * cellW, cy);
    }
  }

  els.placeholder.hidden = true;
  canvas.hidden = false;
}

// ---------- image loading ----------

function showMessage(text) {
  els.placeholder.textContent = text;
  els.placeholder.hidden = false;
  els.output.hidden = true;
}

function loadFile(file) {
  if (!file) return;
  // Some files arrive with an empty MIME type; let the decoder decide in that case.
  if (file.type && !file.type.startsWith("image/")) {
    showMessage(`"${file.name}" is not an image.`);
    return;
  }
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.onload = () => {
    URL.revokeObjectURL(url);
    image = img;
    convert();
  };
  img.onerror = () => {
    URL.revokeObjectURL(url);
    showMessage(`Couldn't read "${file.name}" — this browser may not support that image format.`);
  };
  img.src = url;
}

els.file.addEventListener("change", (e) => loadFile(e.target.files[0]));

["dragenter", "dragover"].forEach((ev) =>
  els.dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    els.dropzone.classList.add("over");
  })
);
["dragleave", "drop"].forEach((ev) =>
  els.dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    els.dropzone.classList.remove("over");
  })
);
els.dropzone.addEventListener("drop", (e) => loadFile(e.dataTransfer.files[0]));

// Paste an image from the clipboard anywhere on the page.
window.addEventListener("paste", (e) => {
  const item = [...e.clipboardData.items].find((i) => i.type.startsWith("image/"));
  if (item) loadFile(item.getAsFile());
});

// ---------- controls ----------

function syncVisibility() {
  els.customWrap.hidden = els.charsetPreset.value !== "custom";
  els.solidWrap.hidden = els.colorMode.value !== "solid";
  els.gradientWrap.hidden = els.colorMode.value !== "gradient";
}

function syncOutputs() {
  for (const id of RANGES) $(id + "Out").textContent = $(id).value;
}

let pending = false;
function scheduleConvert() {
  syncVisibility();
  syncOutputs();
  if (pending) return;
  pending = true;
  requestAnimationFrame(() => {
    pending = false;
    convert();
  });
}

$("controls").addEventListener("input", scheduleConvert);
$("controls").addEventListener("change", scheduleConvert);

// ---------- export ----------

function download(name, href) {
  const a = document.createElement("a");
  a.download = name;
  a.href = href;
  a.click();
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // navigator.clipboard is unavailable outside secure contexts (e.g. http on a LAN IP).
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }
}

$("copyBtn").addEventListener("click", async () => {
  if (!lastText) return;
  const btn = $("copyBtn");
  btn.textContent = (await copyText(lastText)) ? "Copied!" : "Copy failed";
  setTimeout(() => (btn.textContent = "Copy text"), 1200);
});

$("txtBtn").addEventListener("click", () => {
  if (!lastText) return;
  const url = URL.createObjectURL(new Blob([lastText], { type: "text/plain" }));
  download("ascii-art.txt", url);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

$("pngBtn").addEventListener("click", () => {
  if (!image) return;
  download("ascii-art.png", els.output.toDataURL("image/png"));
});

syncVisibility();
syncOutputs();
