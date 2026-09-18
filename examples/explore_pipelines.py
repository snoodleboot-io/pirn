"""Example: visualise all pipelines in the examples folder.

Scans the ``examples/`` directory for pirn pipelines (Python files
containing Tapestry instances) and generates a self-contained HTML
explorer backed by D3.

Run with:
    uv run python examples/explore_pipelines.py

Or use the CLI directly:
    pirn-explore examples/
    pirn-explore examples/ --output my_explorer.html --no-open

The generated file opens automatically in your default browser.
Requires an internet connection (D3 is loaded from CDN).

What you see
------------
* Left sidebar  — all discovered pipelines listed by name and source file.
* Graph canvas  — the selected pipeline rendered as a DAG.
* Orientation   — toggle between vertical (top-down) and horizontal
                  (left-right) layout.
* Zoom / pan    — scroll to zoom, drag to pan.
* Hover         — node tooltip shows knot class and id.
* Edge labels   — parameter names in neon orange.

Before / after (individual pipeline)
-------------------------------------
To render a single pipeline before and after a run use the lower-level
helpers::

    from pirn.viz.tapestry_html_renderer import TapestryHtmlRenderer

    Path("before.html").write_text(TapestryHtmlRenderer.for_tapestry(tapestry))
    # … run the pipeline …
    Path("after.html").write_text(TapestryHtmlRenderer.for_run(result))
"""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import ClassVar

from pirn.viz.explorer_html_generator import ExplorerHtmlGenerator


class ExplorePipelines:
    """Generates the self-contained HTML explorer for every example pipeline."""

    _examples_dir: ClassVar[Path] = Path(__file__).parent
    _output: ClassVar[Path] = _examples_dir / "pirn_explorer.html"

    @classmethod
    def main(cls) -> None:
        """Scan ``examples/``, write the explorer and open it in a browser."""
        print(f"Scanning: {cls._examples_dir}")
        html = ExplorerHtmlGenerator.generate(cls._examples_dir)
        cls._output.write_text(html, encoding="utf-8")
        print(f"Written:  {cls._output}")

        webbrowser.open(cls._output.as_uri())
        print("Opened in browser.")


if __name__ == "__main__":
    ExplorePipelines.main()
