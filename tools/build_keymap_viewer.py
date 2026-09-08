#!/usr/bin/env python3
"""Render the self-contained G13 keymap viewer from data/g13-keymaps.json.

Button placement comes from the arrangement map in Key.java, so the SVG
overlay sits exactly on the buttons in g13.gif (both are 491x710).
"""

import base64
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data", "g13-keymaps.json")
IMAGE = os.path.join(REPO, "src/java/com/gupta/g13/images/g13.gif")
OUT = os.path.join(REPO, "data", "g13-keymap-atlas.html")

TEMPLATE = r"""<title>G13 Keymap Atlas</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@400;600;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root {
  --ground:   #e9ecf1;
  --panel:    #ffffff;
  --stage:    #dfe3ea;
  --ink:      #111620;
  --ink-soft: #4a5665;
  --muted:    #6b7787;
  --line:     #cdd4de;
  --line-soft:#e2e7ee;
  --key:      #0d8f92;
  --key-fill: rgba(13,143,146,.16);
  --macro:    #b06d10;
  --macro-fill: rgba(176,109,16,.16);
  --none:     #97a2b1;
  --none-fill:rgba(151,162,177,.10);
  --focus:    #1d63d6;
  --shadow:   0 1px 2px rgba(16,22,32,.06), 0 8px 24px rgba(16,22,32,.08);
  --r: 10px;
  --sans: "Chivo", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:   #0d1015;
    --panel:    #161b23;
    --stage:    #10141a;
    --ink:      #e7ecf3;
    --ink-soft: #b3bdcb;
    --muted:    #8b96a6;
    --line:     #2a323d;
    --line-soft:#212934;
    --key:      #4ed3cd;
    --key-fill: rgba(78,211,205,.20);
    --macro:    #e2a952;
    --macro-fill: rgba(226,169,82,.20);
    --none:     #6d7887;
    --none-fill:rgba(109,120,135,.14);
    --focus:    #6ea8ff;
    --shadow:   0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.35);
  }
}
:root[data-theme="dark"] {
  --ground:   #0d1015;
  --panel:    #161b23;
  --stage:    #10141a;
  --ink:      #e7ecf3;
  --ink-soft: #b3bdcb;
  --muted:    #8b96a6;
  --line:     #2a323d;
  --line-soft:#212934;
  --key:      #4ed3cd;
  --key-fill: rgba(78,211,205,.20);
  --macro:    #e2a952;
  --macro-fill: rgba(226,169,82,.20);
  --none:     #6d7887;
  --none-fill:rgba(109,120,135,.14);
  --focus:    #6ea8ff;
  --shadow:   0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.35);
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1240px; margin: 0 auto; padding: 32px 24px 64px; }

header { display: flex; flex-wrap: wrap; gap: 16px 28px; align-items: flex-end; justify-content: space-between; margin-bottom: 28px; }
h1 { font-size: clamp(26px, 3.4vw, 38px); font-weight: 800; letter-spacing: -.02em; margin: 0; text-wrap: balance; }
.sub { color: var(--muted); margin: 6px 0 0; max-width: 62ch; }
.tally { display: flex; gap: 22px; font-family: var(--mono); font-size: 12px; color: var(--muted); }
.tally b { display: block; font-family: var(--sans); font-size: 20px; font-weight: 700; color: var(--ink); font-variant-numeric: tabular-nums; }

.layout { display: grid; grid-template-columns: minmax(340px, 460px) 1fr; gap: 26px; align-items: start; }
@media (max-width: 940px) { .layout { grid-template-columns: 1fr; } }

.card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); box-shadow: var(--shadow); }
.stage { position: sticky; top: 20px; padding: 14px; background: var(--stage); }
@media (max-width: 940px) { .stage { position: static; } }
svg.device { display: block; width: 100%; height: auto; }
svg.device .hit { cursor: pointer; transition: fill .12s ease, stroke .12s ease; }
svg.device .hit:focus-visible { outline: none; stroke: var(--focus); stroke-width: 3; }
svg.device .legend { font-family: var(--mono); font-weight: 600; pointer-events: none; user-select: none; }

.controls { display: flex; flex-direction: column; gap: 18px; padding: 20px; }
label.field { display: block; font-size: 11px; letter-spacing: .10em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin-bottom: 7px; }
select {
  width: 100%; padding: 11px 13px; font: inherit; font-size: 15px;
  color: var(--ink); background: var(--panel);
  border: 1px solid var(--line); border-radius: 8px; cursor: pointer;
}
select:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }

.chips { display: flex; flex-wrap: wrap; gap: 7px; }
.chip {
  font-family: var(--mono); font-size: 11.5px; padding: 3px 9px;
  border: 1px solid var(--line); border-radius: 999px; color: var(--ink-soft);
  display: inline-flex; align-items: center; gap: 6px;
}
.chip .swatch { width: 9px; height: 9px; border-radius: 50%; border: 1px solid rgba(128,128,128,.45); }
.chip.warn { border-color: var(--macro); color: var(--macro); }

.readout { border-top: 1px solid var(--line-soft); padding-top: 14px; min-height: 62px; }
.readout .rk { font-family: var(--mono); font-size: 12px; color: var(--muted); letter-spacing: .04em; }
.readout .rv { font-size: 21px; font-weight: 700; letter-spacing: -.01em; }
.readout .rr { font-family: var(--mono); font-size: 12px; color: var(--muted); }

.legend-key { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: var(--muted); }
.legend-key span { display: inline-flex; align-items: center; gap: 6px; }
.legend-key i { width: 11px; height: 11px; border-radius: 3px; border: 1.5px solid; display: inline-block; }

h2 { font-size: 12px; letter-spacing: .11em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin: 0 0 10px; }
.tablewrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th { text-align: left; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 600; padding: 0 12px 8px; border-bottom: 1px solid var(--line); }
td { padding: 7px 12px; border-bottom: 1px solid var(--line-soft); vertical-align: baseline; }
tbody tr { cursor: pointer; }
tbody tr:hover, tbody tr.on { background: var(--none-fill); }
td.k { font-family: var(--mono); font-weight: 600; white-space: nowrap; }
td.v { font-weight: 600; }
td.raw { font-family: var(--mono); font-size: 12px; color: var(--muted); white-space: nowrap; }
.pill { font-family: var(--mono); font-size: 10.5px; padding: 1px 7px; border-radius: 999px; border: 1px solid; }
.pill.key { color: var(--key); border-color: var(--key); }
.pill.macro { color: var(--macro); border-color: var(--macro); }
.pill.off { color: var(--none); border-color: var(--none); }
.note { font-size: 12.5px; color: var(--muted); border-left: 2px solid var(--line); padding-left: 11px; margin: 0; }
footer { margin-top: 34px; padding-top: 18px; border-top: 1px solid var(--line); font-size: 12.5px; color: var(--muted); }
footer a { color: var(--ink-soft); }
.stack { display: flex; flex-direction: column; gap: 20px; }
.pad { padding: 20px; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>

<div class="wrap">
  <header>
    <div>
      <h1>G13 Keymap Atlas</h1>
      <p class="sub">Every published Logitech G13 keymap I could find, normalised into one schema and laid over the real button positions from the driver's own arrangement map.</p>
    </div>
    <div class="tally">
      <div><b id="t-prof">0</b>profiles</div>
      <div><b id="t-bind">0</b>bindings</div>
      <div><b id="t-src">0</b>sources</div>
      <div><b id="t-macro">0</b>macros</div>
    </div>
  </header>

  <div class="layout">
    <div class="card stage">
      <svg class="device" id="device" viewBox="0 0 491 710" role="img" aria-label="Logitech G13 button map"></svg>
    </div>

    <div class="stack">
      <div class="card controls">
        <div>
          <label class="field" for="profile">Keymap</label>
          <select id="profile"></select>
        </div>
        <div class="chips" id="meta"></div>
        <div class="readout" id="readout">
          <div class="rk">Hover or select a button</div>
          <div class="rv">&mdash;</div>
        </div>
        <div class="legend-key">
          <span><i style="border-color:var(--key);background:var(--key-fill)"></i> key</span>
          <span><i style="border-color:var(--macro);background:var(--macro-fill)"></i> macro</span>
          <span><i style="border-color:var(--none);background:var(--none-fill)"></i> unbound</span>
        </div>
      </div>

      <div class="card pad">
        <h2>Bindings</h2>
        <div class="tablewrap"><table>
          <thead><tr><th>Button</th><th>Sends</th><th>Type</th><th>Raw</th></tr></thead>
          <tbody id="rows"></tbody>
        </table></div>
        <p class="note" id="offmap" style="margin-top:14px"></p>
      </div>

      <div class="card pad" id="macrocard" hidden>
        <h2>Macros in this source</h2>
        <div class="tablewrap"><table>
          <thead><tr><th>ID</th><th>Name</th><th>Sequence</th></tr></thead>
          <tbody id="macrorows"></tbody>
        </table></div>
      </div>
    </div>
  </div>

  <footer id="foot"></footer>
</div>

<script>
const DATA = __DATA__;
const IMG = "__IMAGE__";
const SVGNS = "http://www.w3.org/2000/svg";

const byId = id => document.getElementById(id);
const dev = byId("device");
let current = null, pinned = null;

const keyByCode = new Map();
DATA.keys.forEach(k => { if (!keyByCode.has(k.key_code)) keyByCode.set(k.key_code, k); });

function bbox(points) {
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
}

/* ---- build the device overlay once ---- */
const shapes = [];
function buildDevice() {
  const img = document.createElementNS(SVGNS, "image");
  img.setAttribute("href", IMG);
  img.setAttribute("x", 0); img.setAttribute("y", 0);
  img.setAttribute("width", 491); img.setAttribute("height", 710);
  dev.appendChild(img);

  DATA.keys.forEach((k, i) => {
    const box = bbox(k.polygon);
    const poly = document.createElementNS(SVGNS, "polygon");
    poly.setAttribute("points", k.polygon.map(p => p.join(",")).join(" "));
    poly.setAttribute("class", "hit");
    poly.setAttribute("stroke-width", "1.5");
    poly.setAttribute("tabindex", "0");
    poly.setAttribute("role", "button");
    dev.appendChild(poly);

    let text = null;
    if (box.w >= 34 && box.h >= 14) {
      text = document.createElementNS(SVGNS, "text");
      text.setAttribute("class", "legend");
      text.setAttribute("x", box.cx);
      text.setAttribute("y", box.cy);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("dominant-baseline", "central");
      text.setAttribute("font-size", Math.max(9, Math.min(14, box.h * 0.52)));
      dev.appendChild(text);
    }

    const entry = { def: k, poly, text, box, idx: i };
    shapes.push(entry);
    poly.addEventListener("mouseenter", () => setActive(entry, false));
    poly.addEventListener("focus", () => setActive(entry, false));
    poly.addEventListener("mouseleave", () => setActive(null, false));
    poly.addEventListener("click", () => setActive(entry, true));
    poly.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActive(entry, true); }
    });
  });
}

/* ---- profile switching ---- */
function bindingMap(profile) {
  const m = new Map();
  profile.bindings.forEach(b => { if (b.key_code !== null) m.set(b.key_code, b); });
  return m;
}

function shortLegend(text) {
  if (!text) return "";
  if (text.length <= 5) return text;
  return text.slice(0, 4) + "…";
}

function paint(profile) {
  const map = bindingMap(profile);
  shapes.forEach(s => {
    let b = map.get(s.def.key_code);
    const dup = !!s.def.anomaly;
    let stroke = "var(--none)", fill = "var(--none-fill)", label = "";
    if (b && b.action_type === "macro") { stroke = "var(--macro)"; fill = "var(--macro-fill)"; label = b.action_label; }
    else if (b && b.action_type === "none") { b = null; }
    else if (b) { stroke = "var(--key)"; fill = "var(--key-fill)"; label = b.action_label; }
    if (dup) { stroke = "var(--none)"; fill = "none"; label = ""; }
    s.poly.setAttribute("stroke", stroke);
    s.poly.setAttribute("fill", fill);
    s.poly.setAttribute("stroke-dasharray", dup ? "3 3" : "");
    s.binding = b || null;
    const aria = dup ? s.def.key_label + " (duplicate in arrangement map)"
                     : s.def.key_label + ": " + (b ? b.action_label : "unbound");
    s.poly.setAttribute("aria-label", aria);
    if (s.text) {
      s.text.textContent = shortLegend(label);
      s.text.setAttribute("fill", b ? (b.action_type === "macro" ? "var(--macro)" : "var(--key)") : "transparent");
    }
  });
}

function setActive(entry, pin) {
  if (pin) pinned = (pinned === entry) ? null : entry;
  current = entry || pinned;
  shapes.forEach(s => s.poly.setAttribute("stroke-width", s === current ? "3" : "1.5"));
  document.querySelectorAll("#rows tr").forEach(tr => {
    tr.classList.toggle("on", current && tr.dataset.code === String(current.def.key_code));
  });
  const r = byId("readout");
  if (!current) {
    r.innerHTML = '<div class="rk">Hover or select a button</div><div class="rv">&mdash;</div>';
    return;
  }
  const b = current.binding;
  r.innerHTML =
    '<div class="rk">' + current.def.key_label + (current.def.anomaly ? " · duplicate in map" : "") + "</div>" +
    '<div class="rv">' + (b ? escapeHtml(b.action_label) : "unbound") + "</div>" +
    (b ? '<div class="rr">' + escapeHtml(b.action_type === "macro" ? "macro " + b.action_value : "linux keycode " + b.action_value) + "</div>" : "");
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const GROUP_ORDER = ["gkey", "mode", "lcd", "round", "thumb", "stick", "other"];

function renderTable(profile) {
  const tb = byId("rows");
  tb.innerHTML = "";
  const rows = profile.bindings.slice().sort((a, b) => {
    const ga = GROUP_ORDER.indexOf((keyByCode.get(a.key_code) || {}).key_group || "other");
    const gb = GROUP_ORDER.indexOf((keyByCode.get(b.key_code) || {}).key_group || "other");
    return ga - gb || (a.key_code - b.key_code);
  });
  const offmap = [];
  rows.forEach(b => {
    const placed = keyByCode.has(b.key_code);
    if (!placed) offmap.push(b.key_label);
    const tr = document.createElement("tr");
    tr.dataset.code = b.key_code;
    tr.innerHTML =
      '<td class="k">' + escapeHtml(b.key_label) + "</td>" +
      '<td class="v">' + escapeHtml(b.action_label) + "</td>" +
      '<td><span class="pill ' + (b.action_type === "macro" ? "macro" : b.action_type === "none" ? "off" : "key") + '">' +
        (b.action_type === "none" ? "unbound" : b.action_type) + "</span></td>" +
      '<td class="raw">' + escapeHtml(b.action_type === "macro" ? "m," + b.action_value : "k." + b.action_value) + "</td>";
    tr.addEventListener("mouseenter", () => {
      const s = shapes.find(s => s.def.key_code === b.key_code);
      if (s) setActive(s, false);
    });
    tr.addEventListener("mouseleave", () => setActive(null, false));
    tb.appendChild(tr);
  });
  byId("offmap").textContent = offmap.length
    ? "Not drawn on the device: " + [...new Set(offmap)].join(", ") +
      " — these keys are bound in the file but have no polygon in Key.java."
    : "";
}

function renderMeta(profile) {
  const src = DATA.sources.find(s => s.id === profile.source_id) || {};
  const chips = [];
  chips.push('<span class="chip">' + escapeHtml(src.repo || "") + "</span>");
  chips.push('<span class="chip">' + escapeHtml(profile.format) + "</span>");
  chips.push('<span class="chip">' + escapeHtml(profile.origin) + "</span>");
  if (profile.color) {
    const rgb = profile.color.split(",").map(n => parseInt(n, 10) || 0);
    chips.push('<span class="chip"><i class="swatch" style="background:rgb(' + rgb.join(",") + ')"></i>LED ' + escapeHtml(profile.color) + "</span>");
  }
  if (profile.stick_mode) chips.push('<span class="chip">stick ' + escapeHtml(profile.stick_mode) + "</span>");
  const lic = src.license || "";
  chips.push('<span class="chip' + (lic.startsWith("NONE") ? " warn" : "") + '">' + escapeHtml(lic) + "</span>");
  byId("meta").innerHTML = chips.join("");

  const macros = DATA.macros.filter(m => m.source_id === profile.source_id && (m.name || m.sequence));
  const card = byId("macrocard");
  const usesMacros = profile.bindings.some(b => b.action_type === "macro");
  if (usesMacros && macros.length) {
    card.hidden = false;
    byId("macrorows").innerHTML = macros.slice(0, 60).map(m =>
      "<tr><td class=\"k\">" + escapeHtml(m.macro_id) + "</td><td>" + escapeHtml(m.name || "—") +
      "</td><td class=\"raw\">" + escapeHtml(m.sequence || "") + "</td></tr>").join("");
  } else {
    card.hidden = true;
  }
}

function selectProfile(id) {
  const p = DATA.profiles.find(p => p.id === Number(id));
  if (!p) return;
  pinned = null;
  paint(p); renderTable(p); renderMeta(p); setActive(null, false);
}

function init() {
  buildDevice();
  const sel = byId("profile");
  DATA.sources.forEach(src => {
    const list = DATA.profiles.filter(p => p.source_id === src.id);
    if (!list.length) return;
    const g = document.createElement("optgroup");
    g.label = src.repo;
    list.forEach(p => {
      const o = document.createElement("option");
      o.value = p.id; o.textContent = p.name + "  (" + p.bindings.length + " keys)";
      g.appendChild(o);
    });
    sel.appendChild(g);
  });
  sel.addEventListener("change", e => selectProfile(e.target.value));

  byId("t-prof").textContent = DATA.profiles.length;
  byId("t-bind").textContent = DATA.profiles.reduce((n, p) => n + p.bindings.length, 0);
  byId("t-src").textContent = DATA.sources.filter(s => DATA.profiles.some(p => p.source_id === s.id)).length;
  byId("t-macro").textContent = DATA.macros.length;

  byId("foot").innerHTML =
    "Button geometry from <code>src/java/com/gupta/g13/Key.java</code>; key names from <code>JavaToLinuxKeymapping.java</code>. " +
    "Sources: " + DATA.sources.filter(s => s.url).map(s =>
      '<a href="' + s.url + '">' + escapeHtml(s.repo) + "</a>").join(", ") +
    ". Two of these declare no licence, so treat those keymaps as all-rights-reserved rather than reusable. " +
    "Generated " + DATA.generated + ".";

  if (DATA.profiles.length) { sel.value = DATA.profiles[0].id; selectProfile(DATA.profiles[0].id); }
}
init();
</script>
"""


def main():
    bundle = json.load(open(DATA))
    img = "data:image/gif;base64," + base64.b64encode(open(IMAGE, "rb").read()).decode()
    html = TEMPLATE.replace("__DATA__", json.dumps(bundle, separators=(",", ":")))
    html = html.replace("__IMAGE__", img)
    with open(OUT, "w") as fh:
        fh.write(html)
    print("wrote %s (%.1f KB)" % (OUT, os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
