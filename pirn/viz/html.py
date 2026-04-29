"""Standalone HTML renderer for run results.

Produces a single self-contained HTML document with:

* An SVG graph of the run, with nodes colored by outcome.
* Hover tooltips showing knot id, class, outcome, hashes, duration.
* Filter buttons to highlight only ok / err / skipped knots.
* A summary header with run id, duration, and dispatcher.

No external assets — the document includes its own CSS and JS — so
it can be saved and shared as a single file.

The layout uses a simple longest-path layering algorithm rather than
pulling in a graph-layout library; this keeps the output dependency-
free and good enough for typical pipeline shapes (a few dozen nodes).
For very large graphs, render to Mermaid and paste into a tool with
proper layout (mermaid.live, draw.io, etc.).
"""

from __future__ import annotations

import html
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


def html_for_run(result: RunResult, title: str | None = None) -> str:
    """Render a ``RunResult`` to a standalone HTML document."""
    title = title or f"pirn run {result.run_id}"

    # Build node and edge lists from the lineage.
    nodes = [
        {
            "id": rec.knot_id,
            "class": _short(rec.knot_class),
            "outcome": rec.outcome,
            "duration_ms": rec.duration_ms,
            "output_hash": rec.output_hash or "",
            "config_hash": rec.knot_config_hash,
            "error_record_id": rec.error_record_id or "",
            "skip_reason": rec.skip_reason or "",
        }
        for rec in result.lineage
    ]

    by_output = {
        rec.output_hash: rec.knot_id for rec in result.lineage if rec.output_hash is not None
    }
    edges = []
    for rec in result.lineage:
        for input_hash in rec.parent_input_hashes.values():
            parent_kid = by_output.get(input_hash)
            if parent_kid is None:
                continue
            edges.append({"from": parent_kid, "to": rec.knot_id})

    # Layer nodes by longest-path-from-root (= number of ancestors on
    # the longest path).  This produces a topologically-coherent
    # vertical layout.
    layers = _layer_nodes(nodes, edges)
    coords = _assign_coordinates(layers)

    # Render.
    summary_html = _render_summary(result)
    svg = _render_svg(nodes, edges, coords)
    return _DOCUMENT.format(
        title=html.escape(title),
        summary=summary_html,
        svg=svg,
        css=_CSS,
        js=_JS,
    )


# ============================================================ layout


def _get_depth(
    kid: str,
    depth: dict[str, int],
    parents: dict[str, list[str]],
    all_ids: set[str],
    visiting: set[str],
) -> int:
    if kid in depth:
        return depth[kid]
    if kid in visiting:
        return 0
    visiting.add(kid)
    if not parents.get(kid):
        d = 0
    else:
        d = 1 + max(_get_depth(p, depth, parents, all_ids, visiting) for p in parents[kid] if p in all_ids)
    visiting.discard(kid)
    depth[kid] = d
    return d


def _layer_nodes(nodes, edges) -> list[list[str]]:
    """Group nodes into layers by longest path from a root."""
    parents: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        parents[e["to"]].append(e["from"])
    all_ids = {n["id"] for n in nodes}

    depth: dict[str, int] = {}
    for kid in all_ids:
        _get_depth(kid, depth, parents, all_ids, set())

    by_depth: dict[int, list[str]] = defaultdict(list)
    for kid, d in depth.items():
        by_depth[d].append(kid)

    return [sorted(by_depth[d]) for d in sorted(by_depth.keys())]


def _assign_coordinates(layers: list[list[str]]) -> dict[str, tuple[float, float]]:
    """Place each node on a grid of (x, y) pixel coordinates."""
    coords: dict[str, tuple[float, float]] = {}
    layer_height = 110
    horizontal_spacing = 200
    for layer_idx, layer in enumerate(layers):
        n = len(layer)
        # Center the layer horizontally.
        total_width = (n - 1) * horizontal_spacing
        start_x = -total_width / 2
        for i, kid in enumerate(layer):
            x = start_x + i * horizontal_spacing
            y = layer_idx * layer_height + 60
            coords[kid] = (x, y)
    return coords


# ============================================================ rendering


def _render_summary(result) -> str:
    status_class = "succeeded" if result.succeeded else "failed"
    status_label = "succeeded" if result.succeeded else "FAILED"
    return (
        f'<div class="summary">'
        f'<div><span class="label">Run:</span> '
        f'<span class="value">{html.escape(result.run_id)}</span></div>'
        f'<div><span class="label">Status:</span> '
        f'<span class="value status-{status_class}">'
        f"{status_label}</span></div>"
        f'<div><span class="label">Duration:</span> '
        f'<span class="value">{result.duration_seconds:.2f}s</span></div>'
        f'<div><span class="label">Dispatcher:</span> '
        f'<span class="value">{html.escape(result.dispatcher)}</span></div>'
        f"</div>"
    )


def _render_svg(nodes, edges, coords) -> str:
    if not nodes:
        return '<svg><text x="20" y="40">empty run</text></svg>'

    # Compute the SVG viewbox to contain all nodes plus padding.
    xs = [c[0] for c in coords.values()]
    ys = [c[1] for c in coords.values()]
    pad_x, pad_y = 80, 50
    min_x = min(xs) - pad_x
    max_x = max(xs) + pad_x
    min_y = min(ys) - pad_y
    max_y = max(ys) + pad_y
    width = max_x - min_x
    height = max_y - min_y

    parts = [
        f'<svg viewBox="{min_x} {min_y} {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" class="run-svg">'
    ]

    # Edges first so they render under nodes.
    for e in edges:
        if e["from"] not in coords or e["to"] not in coords:
            continue
        x1, y1 = coords[e["from"]]
        x2, y2 = coords[e["to"]]
        # Drop the line to just touch the node boxes.
        y1 += 20  # bottom of the parent box
        y2 -= 20  # top of the child box
        parts.append(
            f'<path d="M {x1},{y1} C {x1},{(y1 + y2) / 2} '
            f'{x2},{(y1 + y2) / 2} {x2},{y2}" class="edge" />'
        )

    # Nodes.
    for node in nodes:
        x, y = coords[node["id"]]
        cls = f"node node-{node['outcome']}"
        parts.append(
            f'<g transform="translate({x},{y})" class="{cls}" '
            f'data-knot-id="{html.escape(node["id"])}" '
            f'data-class="{html.escape(node["class"])}" '
            f'data-outcome="{html.escape(node["outcome"])}" '
            f'data-duration-ms="{node["duration_ms"]}" '
            f'data-output-hash="{html.escape(node["output_hash"])}" '
            f'data-config-hash="{html.escape(node["config_hash"])}" '
            f'data-error="{html.escape(node["error_record_id"])}" '
            f'data-skip-reason="{html.escape(node["skip_reason"])}">'
        )
        parts.append('<rect x="-70" y="-20" width="140" height="40" rx="6" />')
        parts.append(
            f'<text class="node-label" y="-2">{html.escape(_truncate(node["id"], 16))}</text>'
        )
        parts.append(
            f'<text class="node-class" y="14">{html.escape(_truncate(node["class"], 18))}</text>'
        )
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts)


def _short(qualname: str) -> str:
    return qualname.rsplit(".", 1)[-1]


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# ============================================================ assets


_CSS = """
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    margin: 0; padding: 24px; color: #222; background: #fafafa;
}
h1 { margin: 0 0 16px 0; font-size: 22px; }
.summary {
    display: flex; flex-wrap: wrap; gap: 24px; padding: 12px 16px;
    background: #fff; border: 1px solid #ddd; border-radius: 6px;
    margin-bottom: 16px;
}
.summary .label { color: #666; font-size: 13px; margin-right: 6px; }
.summary .value { font-weight: 600; }
.summary .status-succeeded { color: #2d8a39; }
.summary .status-failed { color: #a52a2a; }
.controls {
    display: flex; gap: 8px; margin-bottom: 12px;
}
.controls button {
    padding: 6px 12px; border: 1px solid #ccc; background: #fff;
    border-radius: 4px; cursor: pointer; font-size: 13px;
}
.controls button.active {
    background: #2d8a39; color: white; border-color: #2d8a39;
}
.run-svg {
    width: 100%; height: 70vh; background: #fff;
    border: 1px solid #ddd; border-radius: 6px;
}
.edge { fill: none; stroke: #888; stroke-width: 1.5; }
.node rect {
    stroke-width: 1.5; cursor: pointer;
}
.node text { text-anchor: middle; pointer-events: none; }
.node-label { font-size: 12px; font-weight: 600; }
.node-class { font-size: 10px; fill: #555; }
.node-ok rect { fill: #d1f4d4; stroke: #2d8a39; }
.node-err rect { fill: #fbd5d5; stroke: #a52a2a; }
.node-skipped rect { fill: #e7e7e7; stroke: #888; }
.node-pending rect { fill: #fff3c4; stroke: #b48a14; }
.node.dimmed { opacity: 0.2; }

#tooltip {
    position: absolute; pointer-events: none; background: #222; color: #eee;
    padding: 8px 10px; border-radius: 4px; font-size: 12px; max-width: 320px;
    display: none; z-index: 100;
}
#tooltip dl { margin: 0; display: grid; grid-template-columns: auto auto; gap: 2px 8px; }
#tooltip dt { color: #999; }
#tooltip dd { margin: 0; word-break: break-all; }
"""

_JS = """
(function () {
  var tip = document.getElementById('tooltip');
  document.querySelectorAll('.node').forEach(function (node) {
    node.addEventListener('mousemove', function (ev) {
      var d = node.dataset;
      var rows = [
        ['knot id', d.knotId],
        ['class', d.class],
        ['outcome', d.outcome],
        ['duration', d.durationMs + 'ms'],
        ['output hash', d.outputHash || '(none)'],
        ['config hash', d.configHash],
      ];
      if (d.error) rows.push(['error id', d.error]);
      if (d.skipReason) rows.push(['skip reason', d.skipReason]);
      tip.innerHTML = '<dl>' + rows.map(function (r) {
        return '<dt>' + r[0] + '</dt><dd>' + r[1] + '</dd>';
      }).join('') + '</dl>';
      tip.style.display = 'block';
      tip.style.left = (ev.clientX + 12) + 'px';
      tip.style.top = (ev.clientY + 12) + 'px';
    });
    node.addEventListener('mouseleave', function () {
      tip.style.display = 'none';
    });
  });

  var buttons = document.querySelectorAll('.controls button');
  buttons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var filter = btn.dataset.filter;
      buttons.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      document.querySelectorAll('.node').forEach(function (n) {
        if (filter === 'all' || n.dataset.outcome === filter) {
          n.classList.remove('dimmed');
        } else {
          n.classList.add('dimmed');
        }
      });
    });
  });
})();
"""

_DOCUMENT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<h1>{title}</h1>
{summary}
<div class="controls">
  <button data-filter="all" class="active">All</button>
  <button data-filter="ok">Succeeded</button>
  <button data-filter="err">Failed</button>
  <button data-filter="skipped">Skipped</button>
</div>
{svg}
<div id="tooltip"></div>
<script>{js}</script>
</body>
</html>
"""
