"""Visualization — render tapestries and run results.

* ``mermaid_for_tapestry(tapestry)`` — Mermaid graph syntax for a
  tapestry's structure.  Embed in Markdown docs that support Mermaid
  (GitHub, GitLab, MkDocs, etc.).
* ``mermaid_for_run(result)`` — same but with knot statuses overlaid
  via Mermaid class assignments.
* ``html_for_run(result)`` — standalone HTML/SVG with status colors,
  hover tooltips, and outcome filtering.  Save to a file and open
  in a browser; no server needed.
"""

from pirn.viz.html import html_for_run
from pirn.viz.mermaid import mermaid_for_run, mermaid_for_tapestry

__all__ = [
    "html_for_run",
    "mermaid_for_run",
    "mermaid_for_tapestry",
]
