"""Multi-tapestry graph explorer with execution history.

Generates a self-contained HTML application that renders all tapestries
found in a folder using D3 v7, and surfaces execution history from any
pirn.db files found in the same tree.  Requires internet (D3 from CDN).

Usage::

    from pirn.viz.explorer import generate_explorer_html
    from pathlib import Path
    Path("explorer.html").write_text(generate_explorer_html("/path/to/project"))

Or via the CLI::

    pirn-explore .
    pirn-explore /path/to/project --output explorer.html
"""

from __future__ import annotations

import json
from pathlib import Path


def generate_explorer_html(folder: str | Path) -> str:
    folder = Path(folder).resolve()
    from pirn.viz._scanner import scan_folder

    tapestries, runs = scan_folder(folder)
    data = json.dumps(
        {
            "tapestries": [t.to_dict() for t in tapestries],
            "runs": runs,
            "folder": str(folder),
        },
        indent=2,
    )
    return _TEMPLATE.replace("__EXPLORER_DATA__", data)


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>pirn explorer</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:          #0d0d0d;
  --sidebar:     #0f0f1a;
  --panel:       #0c0c1e;
  --border:      #1e1e3a;
  --purple:      #9d00ff;
  --purple-lo:   #6600bb;
  --purple-hi:   #cc44ff;
  --orange:      #ff6600;
  --orange-hi:   #ff8c33;
  --text:        #e0e0ff;
  --text-dim:    #777;
  --ok:          #00cc66;
  --err:         #ff3333;
  --skip:        #666;
  --tooltip-bg:  #08081a;
  --tooltip-bd:  #9d00ff;
}

:root[data-theme="light"] {
  --bg:          #f4f4f8;
  --sidebar:     #ffffff;
  --panel:       #f0f0f8;
  --border:      #d0d0e0;
  --purple:      #6600cc;
  --purple-lo:   #4400aa;
  --purple-hi:   #8800ee;
  --orange:      #c84400;
  --orange-hi:   #e05000;
  --text:        #1a1a2e;
  --text-dim:    #55557a;
  --ok:          #007a3d;
  --err:         #bb1111;
  --skip:        #777;
  --tooltip-bg:  #ffffff;
  --tooltip-bd:  #6600cc;
}

html, body { height: 100%; background: var(--bg); color: var(--text); font-family: 'JetBrains Mono', 'Fira Code', monospace; overflow: hidden; }
#app { display: flex; height: 100vh; }

/* ── Left sidebar ──────────────────────────────────────────────────────── */
#sidebar {
  width: 220px; min-width: 180px; max-width: 300px;
  background: var(--sidebar); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; overflow: hidden; resize: horizontal;
}
#sidebar-header { padding: 14px 14px 10px; border-bottom: 1px solid var(--border); }
#sidebar-title  { font-size: 15px; font-weight: 700; color: var(--purple); letter-spacing: 0.04em; }
#sidebar-folder { font-size: 9px; color: var(--text-dim); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
#sidebar-count  { font-size: 9px; color: var(--text-dim); margin-top: 2px; }
#tapestry-list  { list-style: none; overflow-y: auto; flex: 1; padding: 6px 0; }
#tapestry-list::-webkit-scrollbar { width: 3px; }
#tapestry-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.tapestry-item {
  padding: 9px 14px; cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.12s, border-color 0.12s;
  font-size: 11px; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tapestry-item:hover  { background: rgba(157,0,255,0.08); border-left-color: var(--purple-lo); }
.tapestry-item.active { background: rgba(157,0,255,0.15); border-left-color: var(--purple); color: var(--purple-hi); }
.tapestry-item .item-source { display: block; font-size: 8px; color: var(--text-dim); margin-top: 2px; }
.tapestry-item.has-error .item-name { color: var(--err); }

/* ── Centre: topbar + graph ────────────────────────────────────────────── */
#main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }

#topbar {
  height: 46px; min-height: 46px;
  background: var(--sidebar); border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 16px; gap: 10px; flex-shrink: 0;
}
#tapestry-title { font-size: 12px; font-weight: 600; color: var(--text); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ctrl-label { font-size: 9px; color: var(--text-dim); margin-right: 2px; }
.btn {
  padding: 4px 10px; font-size: 10px; font-family: inherit;
  background: var(--panel); border: 1px solid var(--border);
  color: var(--text-dim); border-radius: 4px; cursor: pointer; transition: all 0.12s; white-space: nowrap;
}
.btn:hover        { border-color: var(--purple); color: var(--text); }
.btn.active       { background: rgba(157,0,255,0.2); border-color: var(--purple); color: var(--purple-hi); }
.btn.active-hist  { background: rgba(255,102,0,0.15); border-color: var(--orange); color: var(--orange-hi); }
.btn-theme { border-color: var(--text-dim); color: var(--text); font-size: 13px; padding: 3px 9px; }
.btn-theme:hover { border-color: var(--orange); color: var(--orange); }
#stats { font-size: 9px; color: var(--text-dim); white-space: nowrap; }

#loom { flex: 1; position: relative; background: var(--bg); overflow: hidden; }
#loom-svg { position: absolute; inset: 0; width: 100%; height: 100%; }

/* ── Run overlay bar ───────────────────────────────────────────────────── */
#run-bar {
  height: 34px; min-height: 34px;
  background: rgba(255,102,0,0.08); border-top: 1px solid rgba(255,102,0,0.3);
  display: flex; align-items: center; padding: 0 14px; gap: 10px; flex-shrink: 0;
  display: none;
}
#run-bar.visible { display: flex; }
#run-bar-label { font-size: 10px; color: var(--orange); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#run-bar-clear { font-size: 10px; color: var(--text-dim); cursor: pointer; padding: 2px 6px; border: 1px solid var(--border); border-radius: 3px; }
#run-bar-clear:hover { border-color: var(--orange); color: var(--orange); }

/* ── Right history panel ───────────────────────────────────────────────── */
#history-panel {
  width: 0; overflow: hidden;
  background: var(--sidebar); border-left: 1px solid var(--border);
  display: flex; flex-direction: column;
  transition: width 0.2s ease;
  flex-shrink: 0;
}
#history-panel.open { width: 300px; }

#history-header {
  padding: 12px 14px 10px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}
#history-header-title { font-size: 11px; font-weight: 700; color: var(--orange); flex: 1; white-space: nowrap; }
#history-close { font-size: 14px; cursor: pointer; color: var(--text-dim); line-height: 1; }
#history-close:hover { color: var(--text); }

#history-run-count { font-size: 9px; color: var(--text-dim); padding: 6px 14px; border-bottom: 1px solid var(--border); white-space: nowrap; flex-shrink: 0; }

#run-list { overflow-y: auto; flex: 1; }
#run-list::-webkit-scrollbar { width: 3px; }
#run-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

.run-item {
  padding: 10px 14px; cursor: pointer;
  border-left: 3px solid transparent;
  border-bottom: 1px solid var(--border);
  transition: background 0.12s;
}
.run-item:hover  { background: rgba(255,102,0,0.07); }
.run-item.active { background: rgba(255,102,0,0.12); border-left-color: var(--orange); }

.run-item-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.run-status { font-size: 11px; font-weight: 700; }
.run-status.ok  { color: var(--ok); }
.run-status.err { color: var(--err); }
.run-time { font-size: 10px; color: var(--text); flex: 1; }
.run-duration { font-size: 9px; color: var(--text-dim); white-space: nowrap; }
.run-id { font-size: 8px; color: var(--text-dim); }
.run-knot-summary { font-size: 9px; color: var(--text-dim); display: flex; gap: 8px; margin-top: 3px; }
.run-knot-summary .ok-count   { color: var(--ok); }
.run-knot-summary .err-count  { color: var(--err); }
.run-knot-summary .skip-count { color: var(--skip); }

.no-runs { padding: 20px 14px; font-size: 11px; color: var(--text-dim); text-align: center; line-height: 1.6; }

/* ── D3 node/edge styles ───────────────────────────────────────────────── */
.node-group { cursor: pointer; }
.thread-path  { fill: none; stroke: var(--purple); stroke-width: 1.5px; stroke-opacity: 0.55; }
.thread-label { fill: var(--orange); font-size: 9px; font-family: inherit; pointer-events: none; }
.node-class { fill: var(--orange); font-size: 9px; font-family: inherit; pointer-events: none; }
.node-id    { fill: var(--text);   font-size: 11px; font-family: inherit; font-weight: 600; pointer-events: none; }
.node-outcome-badge { font-size: 9px; font-family: inherit; pointer-events: none; }
.empty-msg { fill: var(--text-dim); font-size: 13px; font-family: inherit; }
.error-msg { fill: var(--err);      font-size: 12px; font-family: inherit; }

/* ── Tooltip ───────────────────────────────────────────────────────────── */
#tooltip {
  position: fixed; pointer-events: none; opacity: 0; z-index: 9999;
  background: var(--tooltip-bg); border: 1px solid var(--tooltip-bd); border-radius: 8px;
  padding: 10px 14px; font-size: 11px; color: var(--text); max-width: 300px;
  transition: opacity 0.1s;
  box-shadow: 0 0 18px rgba(157,0,255,0.2), 0 4px 16px rgba(0,0,0,0.25);
}
#tooltip.visible { opacity: 1; }
.tt-class   { color: var(--orange);     font-size: 9px;  margin-bottom: 2px; }
.tt-id      { color: var(--purple-hi);  font-size: 13px; font-weight: 700; margin-bottom: 4px; word-break: break-all; }
.tt-desc    { color: var(--text-dim);   font-size: 9px;  font-style: italic; margin-bottom: 7px; line-height: 1.4; }
.tt-divider { border: none; border-top: 1px solid var(--border); margin: 7px 0; }
.tt-row     { color: var(--text-dim);   font-size: 9px;  margin-top: 3px; line-height: 1.5; }
.tt-row span { color: var(--text); }
.tt-outcome-ok   { color: var(--ok);  font-weight: 700; }
.tt-outcome-err  { color: var(--err); font-weight: 700; }
.tt-outcome-skip { color: var(--skip); font-weight: 700; }

/* ── Knot detail panel (overlays loom, left edge) ─────────────────────── */
#knot-detail {
  position: absolute; left: 0; top: 0; bottom: 0; z-index: 10;
  width: 0; overflow: hidden;
  background: var(--sidebar);
  box-shadow: 2px 0 12px rgba(0,0,0,0.4);
  transition: width 0.2s ease;
  font-size: 11px;
}
#knot-detail.visible { width: 220px; overflow-y: auto; }
#knot-detail::-webkit-scrollbar { width: 3px; }
#knot-detail::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
#knot-detail-inner { padding: 12px 14px; min-width: 220px; }
.kd-header { display: flex; justify-content: flex-end; margin-bottom: 6px; }
.kd-close { font-size: 13px; cursor: pointer; color: var(--text-dim); line-height: 1; }
.kd-close:hover { color: var(--text); }
.kd-divider { border: none; border-top: 1px solid var(--border); margin: 8px 0; }
.kd-w-desc { color: var(--text-dim); font-size: 9px; font-style: italic; line-height: 1.4; margin: 3px 0 6px 0; }

/* 7W row: label + value in a compact two-column layout */
.kd-w-row {
  display: grid; grid-template-columns: 38px 1fr; gap: 4px;
  margin-bottom: 5px; align-items: start;
}
.kd-w-label {
  font-size: 8px; font-weight: 700; letter-spacing: 0.07em;
  color: var(--orange); padding-top: 1px; white-space: nowrap;
}
.kd-w-value { font-size: 10px; color: var(--text); word-break: break-word; line-height: 1.45; }
.kd-w-dim   { color: var(--text-dim); font-size: 9px; }
.w-ok   { color: var(--ok);     font-weight: 700; }
.w-err  { color: var(--err);    font-weight: 700; }
.w-skip { color: var(--skip);   font-weight: 700; }
.kd-hash     { font-size: 8px; color: var(--text-dim); font-family: monospace; margin-top: 3px; word-break: break-all; }
.kd-exc-type { font-size: 10px; font-weight: 700; color: var(--err); margin-top: 4px; }
.kd-exc-msg  { font-size: 9px; color: var(--text); margin-top: 2px; line-height: 1.4; word-break: break-word; }
.kd-exc-tb   {
  font-size: 8px; color: var(--text-dim); font-family: monospace;
  margin-top: 6px; padding: 6px 8px;
  background: rgba(0,0,0,0.25); border-radius: 4px;
  border-left: 2px solid var(--err);
  white-space: pre-wrap; word-break: break-all;
  max-height: 180px; overflow-y: auto; line-height: 1.4;
}
:root[data-theme="light"] .kd-exc-tb { background: #fff0f0; }

/* ── Empty state ───────────────────────────────────────────────────────── */
#empty-state {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 10px; color: var(--text-dim); font-size: 13px; pointer-events: none;
}
#empty-state.hidden { display: none; }
.empty-icon { font-size: 42px; line-height: 1; }
</style>
</head>
<body>
<div id="app">
  <!-- Left sidebar -->
  <div id="sidebar">
    <div id="sidebar-header">
      <div id="sidebar-title">&#x25C6; pirn explorer</div>
      <div id="sidebar-folder"></div>
      <div id="sidebar-count"></div>
    </div>
    <ul id="tapestry-list"></ul>
  </div>

  <!-- Centre -->
  <div id="main">
    <div id="topbar">
      <span id="tapestry-title">Select a tapestry</span>
      <span class="ctrl-label">ORIENTATION</span>
      <button class="btn active" id="btn-vertical"   onclick="setOrientation('vertical')">&#x21D3; Vertical</button>
      <button class="btn"        id="btn-horizontal" onclick="setOrientation('horizontal')">&#x21D2; Horizontal</button>
      <button class="btn" id="btn-history" onclick="toggleHistory()">&#x23F3; Execution History</button>
      <button class="btn btn-theme" id="btn-theme" onclick="toggleTheme()" title="Switch to light mode">&#x263D; Dark</button>
      <div id="stats"></div>
    </div>

    <div id="loom">
      <div id="knot-detail"></div>
      <div id="empty-state">
        <div class="empty-icon">&#x25C6;</div>
        <div>Select a tapestry from the left</div>
      </div>
    </div>

    <div id="run-bar">
      <span id="run-bar-label"></span>
    </div>
  </div>

  <!-- Right history panel -->
  <div id="history-panel">
    <div id="history-header">
      <span id="history-header-title">&#x23F3; Execution History</span>
      <span id="history-close" onclick="toggleHistory()">&#x2715;</span>
    </div>
    <div id="history-run-count"></div>
    <div id="run-list"></div>
  </div>
</div>

<div id="tooltip">
  <div class="tt-class" id="tt-class"></div>
  <div class="tt-id"    id="tt-id"></div>
  <div class="tt-desc"  id="tt-desc"></div>
  <hr  class="tt-divider" id="tt-run-divider" style="display:none">
  <div class="tt-row"   id="tt-outcome"></div>
  <div class="tt-row"   id="tt-duration"></div>
  <div class="tt-row"   id="tt-hash"></div>
  <div class="tt-row"   id="tt-skip"></div>
  <div class="tt-row"   id="tt-err-rec"></div>
  <hr  class="tt-divider" id="tt-run-meta-divider" style="display:none">
  <div class="tt-row"   id="tt-run-id"></div>
  <div class="tt-row"   id="tt-run-dispatcher"></div>
  <div class="tt-row"   id="tt-run-actor"></div>
  <div class="tt-row"   id="tt-run-host"></div>
  <div class="tt-row"   id="tt-run-python"></div>
  <div class="tt-row"   id="tt-run-pirn"></div>
  <div class="tt-row"   id="tt-inputs"></div>
  <div class="tt-row"   id="tt-outputs"></div>
</div>

<script>
const DATA        = __EXPLORER_DATA__;
const TAPESTRIES  = DATA.tapestries;
const RUNS        = DATA.runs;

// ── State ─────────────────────────────────────────────────────────────────────
let current      = null;
let orientation  = 'vertical';
let historyOpen  = false;
let selectedRun  = null;
let theme        = 'dark';
let savedRunIds  = {};  // tapestry name → run_id
let pinnedNode   = null;

const NODE_W = 160, NODE_H = 52, GAP_X = 80, GAP_Y = 72;
const LS_KEY = 'pirn-explorer-v2';

// ── Persistence ───────────────────────────────────────────────────────────────
function saveState() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      tapestry: current ? current.name : null,
      orientation,
      historyOpen,
      savedRunIds,
      theme,
    }));
  } catch (_) {}
}

function loadState() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || '{}'); }
  catch (_) { return {}; }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
setThemeSilent('dark'); // apply before paint; overridden by saved pref below

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('sidebar-folder').textContent = DATA.folder;
  renderSidebar();

  const s = loadState();

  if (s.theme)       setThemeSilent(s.theme);
  if (s.orientation) setOrientationSilent(s.orientation);
  if (s.savedRunIds) savedRunIds = s.savedRunIds;

  const resume = s.tapestry && TAPESTRIES.find(t => t.name === s.tapestry);
  const first  = resume || (TAPESTRIES.length ? TAPESTRIES[0] : null);
  if (first) {
    selectTapestry(first, /*save=*/false);
  }
  if (s.historyOpen) openHistory(/*save=*/false);
  else if (first) renderGraph(); // ensure graph renders even without history
});

// ── Sidebar ───────────────────────────────────────────────────────────────────
function renderSidebar() {
  const count = TAPESTRIES.length;
  document.getElementById('sidebar-count').textContent =
    count === 0 ? 'No tapestries found'
                : `${count} tapestr${count === 1 ? 'y' : 'ies'}`;

  const ul = document.getElementById('tapestry-list');
  ul.innerHTML = '';
  TAPESTRIES.forEach(t => {
    const li = document.createElement('li');
    li.className = 'tapestry-item' + (t.error ? ' has-error' : '');
    li.innerHTML =
      `<span class="item-name">${esc(t.name)}</span>` +
      `<span class="item-source">${esc(t.source)}</span>`;
    li.addEventListener('click', () => selectTapestry(t));
    ul.appendChild(li);
  });
}

function selectTapestry(t, save = true) {
  current     = t;
  selectedRun = null;

  // Restore saved run for this tapestry
  if (historyOpen) {
    const savedId = savedRunIds[t.name];
    const runs    = runsForTapestry(t);
    selectedRun   = (savedId && runs.find(r => r.run_id === savedId)) || runs[0] || null;
  }

  updateRunBar();
  document.querySelectorAll('.tapestry-item').forEach((el, i) => {
    el.classList.toggle('active', TAPESTRIES[i] === t);
  });
  document.getElementById('tapestry-title').textContent = t.name;
  updateStats(t);
  document.getElementById('empty-state').classList.add('hidden');
  hideTooltip();
  hideKnotDetail();
  if (historyOpen) renderRunList(t);
  if (save) saveState();
  renderGraph();
}

function updateStats(t) {
  document.getElementById('stats').textContent =
    t.error ? '⚠ parse error'
    : `${t.nodes.length} knot${t.nodes.length === 1 ? '' : 's'} · ${t.edges.length} thread${t.edges.length === 1 ? '' : 's'}`;
}

// ── Orientation ───────────────────────────────────────────────────────────────
function setOrientation(o) {
  setOrientationSilent(o);
  saveState();
  if (current) renderGraph();
}

function setOrientationSilent(o) {
  orientation = o;
  document.getElementById('btn-vertical').classList.toggle('active',   o === 'vertical');
  document.getElementById('btn-horizontal').classList.toggle('active', o === 'horizontal');
}

// ── Theme ─────────────────────────────────────────────────────────────────────
function toggleTheme() {
  setTheme(theme === 'dark' ? 'light' : 'dark');
}

function setTheme(t) {
  setThemeSilent(t);
  saveState();
  if (current) renderGraph();
}

function setThemeSilent(t) {
  theme = t;
  document.documentElement.setAttribute('data-theme', t);
  const btn = document.getElementById('btn-theme');
  if (btn) {
    btn.innerHTML = t === 'dark' ? '&#x263D; Dark' : '&#x2600; Light';
    btn.title = t === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
  }
}

// ── History panel ─────────────────────────────────────────────────────────────
function toggleHistory() {
  historyOpen ? closeHistory() : openHistory();
}

function openHistory(save = true) {
  historyOpen = true;
  document.getElementById('history-panel').classList.add('open');
  document.getElementById('btn-history').classList.add('active-hist');
  if (current) {
    // Auto-select saved run, or fall back to the first run
    if (!selectedRun) {
      const savedId = savedRunIds[current.name];
      const runs    = runsForTapestry(current);
      selectedRun   = (savedId && runs.find(r => r.run_id === savedId)) || runs[0] || null;
    }
    renderRunList(current);
    updateRunBar();
    renderGraph();
  }
  if (save) saveState();
}

function closeHistory() {
  historyOpen = false;
  selectedRun = null;
  document.getElementById('history-panel').classList.remove('open');
  document.getElementById('btn-history').classList.remove('active-hist');
  updateRunBar();
  renderGraph();
  saveState();
}

function runsForTapestry(tapestry) {
  const nodeIds = new Set(tapestry.nodes.map(n => n.id));
  return RUNS.filter(r => {
    const runKnots = Object.keys(r.knots);
    if (!runKnots.length) return false;
    const overlap = runKnots.filter(k => nodeIds.has(k)).length;
    return overlap / runKnots.length >= 0.4;
  });
}

function renderRunList(tapestry) {
  const runs = runsForTapestry(tapestry);
  const countEl = document.getElementById('history-run-count');
  countEl.textContent = runs.length
    ? `${runs.length} run${runs.length === 1 ? '' : 's'} recorded`
    : 'No recorded runs for this tapestry';

  const listEl = document.getElementById('run-list');
  listEl.innerHTML = '';

  if (!runs.length) {
    listEl.innerHTML = `<div class="no-runs">No runs found.<br>Run the tapestry to record execution history.</div>`;
    return;
  }

  runs.forEach(r => {
    const okCount   = Object.values(r.knots).filter(k => k.outcome === 'ok').length;
    const errCount  = Object.values(r.knots).filter(k => k.outcome === 'err').length;
    const skipCount = Object.values(r.knots).filter(k => k.outcome === 'skipped').length;
    const statusCls = r.succeeded ? 'ok' : 'err';
    const statusCh  = r.succeeded ? '✓' : '✗';
    const ts        = fmtTime(r.started_at);
    const dur       = fmtDuration(r.duration_ms);

    const el = document.createElement('div');
    el.className = 'run-item' + (selectedRun && selectedRun.run_id === r.run_id ? ' active' : '');
    el.innerHTML = `
      <div class="run-item-header">
        <span class="run-status ${statusCls}">${statusCh}</span>
        <span class="run-time">${esc(ts)}</span>
        <span class="run-duration">${esc(dur)}</span>
      </div>
      <div class="run-id">${esc(r.run_id.slice(0, 32))}…</div>
      <div class="run-knot-summary">
        <span class="ok-count">✓ ${okCount}</span>
        ${errCount  ? `<span class="err-count">✗ ${errCount}</span>`   : ''}
        ${skipCount ? `<span class="skip-count">⊘ ${skipCount}</span>` : ''}
      </div>`;
    el.addEventListener('click', () => selectRun(r));
    listEl.appendChild(el);
  });
}

// ── Run selection ─────────────────────────────────────────────────────────────
function selectRun(run, save = true) {
  selectedRun = run;
  if (current && run) savedRunIds[current.name] = run.run_id;
  document.querySelectorAll('.run-item').forEach((el, i) => {
    const runs = runsForTapestry(current);
    el.classList.toggle('active', runs[i] === run);
  });
  updateRunBar();
  if (save) saveState();
  renderGraph();
}

function updateRunBar() {
  const bar = document.getElementById('run-bar');
  if (selectedRun) {
    bar.classList.add('visible');
    document.getElementById('run-bar-label').textContent =
      `Viewing run ${selectedRun.run_id.slice(0, 20)}…  ·  ${fmtTime(selectedRun.started_at)}  ·  ${fmtDuration(selectedRun.duration_ms)}`;
  } else {
    bar.classList.remove('visible');
  }
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
const ttEl = document.getElementById('tooltip');

function showTooltip(event, node) {
  document.getElementById('tt-class').textContent = node.class;
  document.getElementById('tt-id').textContent    = node.id;
  _ttRow('tt-desc', node.description, '');

  const runDivider     = document.getElementById('tt-run-divider');
  const runMetaDivider = document.getElementById('tt-run-meta-divider');

  if (selectedRun) {
    const k = selectedRun.knots[node.id];
    runDivider.style.display = '';

    if (k) {
      const ocCls = k.outcome === 'ok' ? 'tt-outcome-ok' : k.outcome === 'err' ? 'tt-outcome-err' : 'tt-outcome-skip';
      const ocCh  = k.outcome === 'ok' ? '✓ ok' : k.outcome === 'err' ? '✗ err' : '⊘ skipped';
      document.getElementById('tt-outcome').innerHTML  = `outcome: <span class="${ocCls}">${ocCh}</span>`;
      document.getElementById('tt-outcome').style.display = '';
      _ttRow('tt-duration', k.duration_ms != null ? `${k.duration_ms} ms` : '', 'duration: ');
      _ttRow('tt-hash',     k.output_hash ? k.output_hash.slice(0, 28) + '…' : '', 'hash: ');
      _ttRow('tt-skip',     k.skip_reason,    'skipped: ');
      _ttRow('tt-err-rec',  k.error_record_id, 'error id: ');
    } else {
      ['tt-outcome','tt-duration','tt-hash','tt-skip','tt-err-rec'].forEach(id => {
        document.getElementById(id).style.display = 'none';
      });
    }

    runMetaDivider.style.display = '';
    _ttRow('tt-run-id',         selectedRun.run_id.slice(0, 28) + '…', 'run: ');
    _ttRow('tt-run-dispatcher', selectedRun.dispatcher,  'dispatcher: ');
    _ttRow('tt-run-actor',      selectedRun.actor,       'actor: ');
    _ttRow('tt-run-host',       selectedRun.environment && selectedRun.environment.hostname, 'host: ');
    _ttRow('tt-run-python',     selectedRun.runtime_info && selectedRun.runtime_info.python_version
                                  ? selectedRun.runtime_info.python_version.split(' ')[0] + ' ' + selectedRun.runtime_info.python_version.split(' ')[1]
                                  : '', 'python: ');
    _ttRow('tt-run-pirn',       selectedRun.runtime_info && selectedRun.runtime_info.pirn_version, 'pirn: ');
  } else {
    runDivider.style.display     = 'none';
    runMetaDivider.style.display = 'none';
    ['tt-outcome','tt-duration','tt-hash','tt-skip','tt-err-rec',
     'tt-run-id','tt-run-dispatcher','tt-run-actor','tt-run-host','tt-run-python','tt-run-pirn'].forEach(id => {
      document.getElementById(id).style.display = 'none';
    });
  }

  // Edge labels (inputs/outputs)
  const t = current;
  const inEdges  = t.edges.filter(e => e.target === node.id);
  const outEdges = t.edges.filter(e => e.source === node.id);
  if (inEdges.length) {
    const s = inEdges.map(e => e.label ? `<span>${esc(e.label)}</span>←${esc(e.source)}` : esc(e.source)).join(', ');
    document.getElementById('tt-inputs').innerHTML = `receives from: ${s}`;
    document.getElementById('tt-inputs').style.display = '';
  } else {
    document.getElementById('tt-inputs').style.display = 'none';
  }
  if (outEdges.length) {
    const s = outEdges.map(e => `<span>${esc(e.target)}</span>`).join(', ');
    document.getElementById('tt-outputs').innerHTML = `passes to: ${s}`;
    document.getElementById('tt-outputs').style.display = '';
  } else {
    document.getElementById('tt-outputs').style.display = 'none';
  }

  positionTooltip(event);
  ttEl.classList.add('visible');
}

function _ttRow(id, val, prefix) {
  const el = document.getElementById(id);
  if (val) {
    el.innerHTML = `${prefix}<span>${esc(String(val))}</span>`;
    el.style.display = '';
  } else {
    el.style.display = 'none';
  }
}

// ── Pinned knot detail (sidebar) ──────────────────────────────────────────────
function toggleKnotDetail(node) {
  if (pinnedNode && pinnedNode.id === node.id) { hideKnotDetail(); return; }
  showKnotDetail(node);
}

function showKnotDetail(node) {
  pinnedNode = node;
  const el = document.getElementById('knot-detail');
  const t  = current;
  const inEdges  = t.edges.filter(e => e.target === node.id);
  const outEdges = t.edges.filter(e => e.source === node.id);
  const k = selectedRun ? selectedRun.knots[node.id] : null;
  const r = selectedRun;

  // ── Header ────────────────────────────────────────────────────────────
  let html = `<div id="knot-detail-inner">
    <div class="kd-header">
      <span class="kd-close" onclick="hideKnotDetail()">&#x2715;</span>
    </div>`;

  // ── 7W rows ───────────────────────────────────────────────────────────
  function w(label, value, cls) {
    if (!value && value !== 0) return '';
    return `<div class="kd-w-row">
      <span class="kd-w-label">${label}</span>
      <span class="kd-w-value${cls ? ' ' + cls : ''}">${value}</span>
    </div>`;
  }

  // WHAT — always present
  const ocCls = !k ? '' : k.outcome === 'ok' ? 'w-ok' : k.outcome === 'err' ? 'w-err' : 'w-skip';
  const ocBadge = !k ? '' : k.outcome === 'ok' ? '✓ ok' : k.outcome === 'err' ? '✗ err' : '⊘ skipped';
  const whatVal = k
    ? `<span class="${ocCls}">${ocBadge}</span> <span class="kd-w-dim">${esc(node.class)}</span>`
    : `<span class="kd-w-dim">${esc(node.class)}</span>`;
  html += `<div class="kd-w-row"><span class="kd-w-label">WHAT</span><div class="kd-w-value">${esc(node.id)}<br>${whatVal}</div></div>`;
  if (node.description) html += `<div class="kd-w-desc">${esc(node.description)}</div>`;

  // HOW — connections (always present)
  let howParts = [];
  inEdges.forEach(e  => howParts.push(`<span class="kd-w-dim">← ${esc(e.label || e.source)}</span>`));
  outEdges.forEach(e => howParts.push(`<span class="kd-w-dim">→ ${esc(e.target)}</span>`));
  if (howParts.length) {
    html += `<div class="kd-w-row"><span class="kd-w-label">HOW</span><div class="kd-w-value">${howParts.join('<br>')}</div></div>`;
  }

  if (r) {
    html += `<hr class="kd-divider">`;

    // WHO
    html += w('WHO', esc(r.actor) || '—');

    // WHEN — knot-level timing if available, else run timing
    const kWhen = k && k.started_at
      ? `${fmtTime(k.started_at)}<br><span class="kd-w-dim">${fmtDuration(k.duration_ms)}</span>`
      : `${fmtTime(r.started_at)}<br><span class="kd-w-dim">${fmtDuration(r.duration_ms)} total</span>`;
    html += `<div class="kd-w-row"><span class="kd-w-label">WHEN</span><div class="kd-w-value">${kWhen}</div></div>`;

    // WHERE
    const host = r.environment && r.environment.hostname;
    html += w('WHERE', host ? esc(host) : '');

    // HOW (execution) — dispatcher
    html += w('HOW', esc(r.dispatcher));

    // WHY — trigger + skip reason
    const why = [r.trigger, k && k.skip_reason ? `cached: ${k.skip_reason}` : ''].filter(Boolean).join(' · ');
    html += w('WHY', why ? esc(why) : '');

    // WHICH — versions + config hash
    const rt = r.runtime_info || {};
    const pyVer = rt.python_version ? rt.python_version.split(' ').slice(0,2).join(' ') : '';
    const pirnVer = rt.pirn_version ? `pirn ${rt.pirn_version}` : '';
    const cfgHash = k && k.knot_config_hash ? `cfg ${k.knot_config_hash.slice(0,10)}…` : '';
    const which = [pyVer, pirnVer, cfgHash].filter(Boolean).join('<br>');
    if (which) html += `<div class="kd-w-row"><span class="kd-w-label">WHICH</span><div class="kd-w-value kd-w-dim">${which}</div></div>`;

    html += `<hr class="kd-divider">`;

    // Output hash
    if (k && k.output_hash) {
      html += `<div class="kd-hash" title="${esc(k.output_hash)}">out&nbsp;${esc(k.output_hash.slice(0,22))}…</div>`;
    }

    // Error detail
    if (k && k.error_record_id) {
      const exc = r.exceptions && r.exceptions[k.error_record_id];
      if (exc) {
        html += `<div class="kd-exc-type">${esc(exc.exc_type)}</div>`;
        html += `<div class="kd-exc-msg">${esc(exc.message)}</div>`;
        html += `<pre class="kd-exc-tb">${esc(exc.traceback_text)}</pre>`;
      } else {
        html += `<div class="kd-hash w-err">err&nbsp;${esc(k.error_record_id.slice(0,22))}…</div>`;
      }
    }
  }

  html += `</div>`;
  el.innerHTML = html;
  el.classList.add('visible');
}

function hideKnotDetail() {
  pinnedNode = null;
  const el = document.getElementById('knot-detail');
  el.classList.remove('visible');
  el.innerHTML = '';
}

function positionTooltip(event) {
  const PAD = 14, tw = ttEl.offsetWidth || 240, th = ttEl.offsetHeight || 120;
  let x = event.clientX + PAD, y = event.clientY + PAD;
  if (x + tw > window.innerWidth  - PAD) x = event.clientX - tw - PAD;
  if (y + th > window.innerHeight - PAD) y = event.clientY - th - PAD;
  ttEl.style.left = x + 'px'; ttEl.style.top = y + 'px';
}

function hideTooltip() { ttEl.classList.remove('visible'); }
document.addEventListener('mousemove', e => { if (ttEl.classList.contains('visible')) positionTooltip(e); });

// ── Layout ────────────────────────────────────────────────────────────────────
function computeLayout(nodes, edges) {
  if (!nodes.length) return { positions: new Map() };

  const childMap = new Map(nodes.map(n => [n.id, []]));
  const inDeg    = new Map(nodes.map(n => [n.id, 0]));
  for (const e of edges) {
    if (childMap.has(e.source) && inDeg.has(e.target)) {
      childMap.get(e.source).push(e.target);
      inDeg.set(e.target, inDeg.get(e.target) + 1);
    }
  }

  const layer = new Map(nodes.map(n => [n.id, 0]));
  const queue = nodes.filter(n => inDeg.get(n.id) === 0).map(n => n.id);
  const order = [];
  while (queue.length) {
    const id = queue.shift(); order.push(id);
    for (const ch of (childMap.get(id) || [])) {
      layer.set(ch, Math.max(layer.get(ch), layer.get(id) + 1));
      inDeg.set(ch, inDeg.get(ch) - 1);
      if (inDeg.get(ch) === 0) queue.push(ch);
    }
  }
  for (const n of nodes) if (!order.includes(n.id)) order.push(n.id);

  const maxL  = Math.max(...[...layer.values()], 0);
  const groups = Array.from({ length: maxL + 1 }, () => []);
  for (const id of order) groups[layer.get(id) ?? 0].push(id);

  const pos = new Map();
  if (orientation === 'vertical') {
    for (let l = 0; l < groups.length; l++) {
      const g = groups[l], span = g.length * NODE_W + (g.length - 1) * GAP_X;
      for (let i = 0; i < g.length; i++)
        pos.set(g[i], { x: -span/2 + i*(NODE_W+GAP_X) + NODE_W/2, y: l*(NODE_H+GAP_Y) });
    }
  } else {
    for (let l = 0; l < groups.length; l++) {
      const g = groups[l], span = g.length * NODE_H + (g.length - 1) * GAP_Y;
      for (let i = 0; i < g.length; i++)
        pos.set(g[i], { x: l*(NODE_W+GAP_X), y: -span/2 + i*(NODE_H+GAP_Y) + NODE_H/2 });
    }
  }
  return { positions: pos };
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderGraph() {
  if (!current) return;
  const tapestry = current;
  const container = document.getElementById('loom');
  const W = container.clientWidth, H = container.clientHeight;

  d3.select('#loom-svg').remove();
  const svg = d3.select('#loom').append('svg').attr('id', 'loom-svg');

  if (tapestry.error) {
    svg.append('text').attr('class','error-msg').attr('x',W/2).attr('y',H/2).attr('text-anchor','middle').text(`Parse error: ${tapestry.error}`);
    return;
  }
  if (!tapestry.nodes.length) {
    svg.append('text').attr('class','empty-msg').attr('x',W/2).attr('y',H/2).attr('text-anchor','middle').text('No knots found');
    return;
  }

  // ── Defs ──────────────────────────────────────────────────────────────────
  const defs = svg.append('defs');

  function mkGrad(id, stops) {
    const g = defs.append('linearGradient').attr('id', id)
      .attr('x1','0%').attr('y1','100%').attr('x2','100%').attr('y2','0%');
    stops.forEach(([off, col]) => g.append('stop').attr('offset', off).attr('stop-color', col));
  }

  const isDark = theme !== 'light';
  if (isDark) {
    mkGrad('ng-base',    [['0%','#3a0a00'],['45%','#1a0a2e'],['100%','#200040']]);
    mkGrad('ng-hover',   [['0%','#5a1200'],['45%','#2d1050'],['100%','#3a0070']]);
    mkGrad('ng-ok',      [['0%','#002a12'],['45%','#0a1a1a'],['100%','#10003a']]);
    mkGrad('ng-err',     [['0%','#2a0000'],['45%','#1a0a1a'],['100%','#20003a']]);
    mkGrad('ng-skipped', [['0%','#141414'],['45%','#111118'],['100%','#18181a']]);
  } else {
    mkGrad('ng-base',    [['0%','#f0e4ff'],['50%','#fdf0e8'],['100%','#ffe8d4']]);
    mkGrad('ng-hover',   [['0%','#e0caff'],['50%','#fce0c8'],['100%','#ffd4b8']]);
    mkGrad('ng-ok',      [['0%','#d4fae8'],['50%','#eafaf0'],['100%','#f0fff6']]);
    mkGrad('ng-err',     [['0%','#ffd4d4'],['50%','#ffeaea'],['100%','#fff4f4']]);
    mkGrad('ng-skipped', [['0%','#e8e8f0'],['50%','#f0f0f8'],['100%','#f8f8fc']]);
  }

  const arrowColor = isDark ? '#9d00ff' : '#6600cc';
  const filt = defs.append('filter').attr('id','glow').attr('x','-30%').attr('y','-30%').attr('width','160%').attr('height','160%');
  filt.append('feGaussianBlur').attr('stdDeviation','3').attr('result','blur');
  const mg = filt.append('feMerge');
  mg.append('feMergeNode').attr('in','blur');
  mg.append('feMergeNode').attr('in','SourceGraphic');

  defs.append('marker').attr('id','arrow')
    .attr('viewBox','0 -5 10 10').attr('refX',9).attr('refY',0)
    .attr('markerWidth',6).attr('markerHeight',6).attr('orient','auto')
    .append('path').attr('d','M0,-5L10,0L0,5').attr('fill', arrowColor);

  // ── Zoom ──────────────────────────────────────────────────────────────────
  const zoom = d3.zoom().scaleExtent([0.08,5])
    .on('zoom', e => { g.attr('transform', e.transform); hideTooltip(); });
  svg.call(zoom).on('click', () => { hideTooltip(); hideKnotDetail(); });
  const g = svg.append('g');

  const { positions } = computeLayout(tapestry.nodes, tapestry.edges);

  const xs = [...positions.values()].map(p=>p.x), ys = [...positions.values()].map(p=>p.y);
  const minX=Math.min(...xs)-NODE_W/2, maxX=Math.max(...xs)+NODE_W/2;
  const minY=Math.min(...ys)-NODE_H/2, maxY=Math.max(...ys)+NODE_H/2;
  const gW=maxX-minX, gH=maxY-minY;
  const sc = Math.min(1, Math.min((W-80)/gW, (H-80)/gH));
  svg.call(zoom.transform, d3.zoomIdentity.translate(W/2-sc*(minX+gW/2), H/2-sc*(minY+gH/2)).scale(sc));

  // ── Edges ─────────────────────────────────────────────────────────────────
  const edgeG = g.append('g');
  for (const e of tapestry.edges) {
    const s = positions.get(e.source), t = positions.get(e.target);
    if (!s || !t) continue;
    let sx, sy, tx2, ty2, cx1, cy1, cx2, cy2;
    if (orientation === 'vertical') {
      sx=s.x; sy=s.y+NODE_H/2; tx2=t.x; ty2=t.y-NODE_H/2;
      cx1=sx; cy1=(sy+ty2)/2; cx2=tx2; cy2=cy1;
    } else {
      sx=s.x+NODE_W/2; sy=s.y; tx2=t.x-NODE_W/2; ty2=t.y;
      cx1=(sx+tx2)/2; cy1=sy; cx2=cx1; cy2=ty2;
    }
    edgeG.append('path').attr('class','thread-path')
      .attr('d',`M${sx},${sy} C${cx1},${cy1} ${cx2},${cy2} ${tx2},${ty2}`)
      .attr('marker-end','url(#arrow)');
    if (e.label) {
      edgeG.append('text').attr('class','thread-label')
        .attr('x',(sx+tx2)/2).attr('y',(sy+ty2)/2-5).attr('text-anchor','middle').text(e.label);
    }
  }

  // ── Nodes ─────────────────────────────────────────────────────────────────
  const nodeG = g.append('g');
  for (const n of tapestry.nodes) {
    const pos = positions.get(n.id);
    if (!pos) continue;

    // Determine outcome style
    const c = {
      base:    isDark ? '#9d00ff' : '#6600cc',
      ok:      isDark ? '#00cc66' : '#007a3d',
      err:     isDark ? '#ff3333' : '#bb1111',
      skip:    isDark ? '#555'    : '#888',
    };
    let gradId = 'ng-base', stroke = c.base, strokeW = 1.5, opacity = 1, badge = '';
    if (selectedRun) {
      const k = selectedRun.knots[n.id];
      if (k) {
        if      (k.outcome === 'ok')      { gradId='ng-ok';      stroke=c.ok;   badge='✓'; }
        else if (k.outcome === 'err')     { gradId='ng-err';     stroke=c.err;  badge='✗'; }
        else if (k.outcome === 'skipped') { gradId='ng-skipped'; stroke=c.skip; badge='⊘'; }
      } else {
        opacity = 0.3;
      }
    }

    const ng = nodeG.append('g')
      .attr('class','node-group')
      .attr('transform',`translate(${pos.x-NODE_W/2},${pos.y-NODE_H/2})`)
      .attr('opacity', opacity);

    const rect = ng.append('rect')
      .attr('width',NODE_W).attr('height',NODE_H).attr('rx',9)
      .attr('fill',`url(#${gradId})`).attr('stroke',stroke).attr('stroke-width',strokeW);

    ng.append('text').attr('class','node-class')
      .attr('x',NODE_W/2).attr('y',18).attr('text-anchor','middle')
      .text(n.class.length>22 ? n.class.slice(0,21)+'…' : n.class);

    ng.append('text').attr('class','node-id')
      .attr('x',NODE_W/2).attr('y',36).attr('text-anchor','middle')
      .text(n.id.length>17 ? n.id.slice(0,16)+'…' : n.id);

    if (badge) {
      const badgeColor = badge==='✓' ? c.ok : badge==='✗' ? c.err : c.skip;
      ng.append('text').attr('class','node-outcome-badge')
        .attr('x',NODE_W-8).attr('y',14).attr('text-anchor','end').attr('fill',badgeColor)
        .text(badge);
    }

    ng.on('mouseenter', function(event) {
      if (opacity > 0.5) {
        rect.attr('fill',`url(#ng-hover)`).attr('stroke-width',2).attr('filter','url(#glow)');
      }
      showTooltip(event, n);
    }).on('mousemove', positionTooltip)
      .on('mouseleave', function() {
        rect.attr('fill',`url(#${gradId})`).attr('stroke-width',strokeW).attr('filter',null);
        hideTooltip();
      })
      .on('click', function(event) {
        event.stopPropagation();
        hideTooltip();
        toggleKnotDetail(n);
      });
  }
}

// ── Formatting ────────────────────────────────────────────────────────────────
function fmtDuration(ms) {
  if (ms == null) return '';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms/1000).toFixed(2)}s`;
  return `${Math.floor(ms/60000)}m ${Math.floor((ms%60000)/1000)}s`;
}

function fmtTime(iso) {
  try {
    const d = new Date(iso.replace(' ','T'));
    return d.toLocaleString(undefined, {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
  } catch (_) { return iso; }
}

function esc(s) {
  return String(s||'')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
</script>
</body>
</html>
"""
