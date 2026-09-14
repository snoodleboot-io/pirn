"""Visualization — render tapestries and run results.

* ``MermaidRenderer.for_tapestry(tapestry)`` — Mermaid graph syntax for a
  tapestry's structure.  Embed in Markdown docs that support Mermaid
  (GitHub, GitLab, MkDocs, etc.).
* ``MermaidRenderer.for_run(result)`` — same but with knot statuses overlaid
  via Mermaid class assignments.
* ``TapestryHtmlRenderer.for_run(result)`` — standalone HTML/SVG with status colors,
  hover tooltips, and outcome filtering.  Save to a file and open
  in a browser; no server needed.
"""
