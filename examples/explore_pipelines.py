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

    from pirn.viz.html import html_for_tapestry, html_for_run

    Path("before.html").write_text(html_for_tapestry(tapestry))
    # … run the pipeline …
    Path("after.html").write_text(html_for_run(result))
"""

from __future__ import annotations

from pathlib import Path

from pirn.viz.explorer import generate_explorer_html

EXAMPLES_DIR = Path(__file__).parent
OUTPUT = EXAMPLES_DIR / "pirn_explorer.html"


def main() -> None:
    print(f"Scanning: {EXAMPLES_DIR}")
    html = generate_explorer_html(EXAMPLES_DIR)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Written:  {OUTPUT}")

    import webbrowser
    webbrowser.open(OUTPUT.as_uri())
    print("Opened in browser.")


if __name__ == "__main__":
    main()
