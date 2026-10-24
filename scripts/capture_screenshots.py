"""Headless screenshot capture for pirn Explorer documentation.

Serves examples/pirn_explorer.html via a local HTTP server, drives it with
Playwright, and writes PNGs to docs/assets/screenshots/.

Usage:
    uv run --extra docs python scripts/capture_screenshots.py
    # or after `pip install playwright && playwright install chromium`
    python scripts/capture_screenshots.py

The script re-generates every screenshot referenced in docs/guides/visualization.md.
"""

from __future__ import annotations

import functools
import http.server
import pathlib
import threading
import time
from typing import ClassVar

from playwright.sync_api import Page, sync_playwright

from gatekit.silent_http_request_handler import SilentHttpRequestHandler


class CaptureScreenshots:
    """Drive the Explorer page with Playwright and write the documentation PNGs."""

    _repo: ClassVar[pathlib.Path] = pathlib.Path(__file__).resolve().parent.parent
    _examples_dir: ClassVar[pathlib.Path] = (
        pathlib.Path(__file__).resolve().parent.parent / "examples"
    )
    _out_dir: ClassVar[pathlib.Path] = (
        pathlib.Path(__file__).resolve().parent.parent / "docs" / "assets" / "screenshots"
    )
    _viewport: ClassVar[dict[str, int]] = {"width": 1440, "height": 900}

    # -- local HTTP server (serves examples/ so the CDN scripts load) --------

    @staticmethod
    def _start_server(directory: pathlib.Path) -> tuple[int, threading.Thread]:
        handler = functools.partial(SilentHttpRequestHandler, directory=str(directory))
        server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return port, thread

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _wait_for_graph(page: Page) -> None:
        """Wait until at least one node-group is visible in the SVG."""
        page.wait_for_selector(".node-group", timeout=10_000)
        time.sleep(0.4)  # let D3 finish layout animations

    @staticmethod
    def _select_pipeline(page: Page, name: str) -> None:
        """Click a pipeline in the sidebar by name."""
        page.locator(".tapestry-item").filter(has_text=name).first.click()
        CaptureScreenshots._wait_for_graph(page)

    @staticmethod
    def _open_history(page: Page) -> None:
        """Open the run history panel if it is not already open."""
        panel = page.locator("#history-panel")
        if "open" not in (panel.get_attribute("class") or ""):
            page.click("#btn-history")
            page.wait_for_selector("#history-panel.open", timeout=5_000)
            time.sleep(0.2)

    @staticmethod
    def _close_history(page: Page) -> None:
        panel = page.locator("#history-panel")
        if "open" in (panel.get_attribute("class") or ""):
            page.click("#btn-history")
            time.sleep(0.2)

    @staticmethod
    def _select_first_run(page: Page) -> None:
        """Click the first run item in the history panel to overlay outcomes."""
        CaptureScreenshots._open_history(page)
        page.locator(".run-item").first.click()
        time.sleep(0.3)

    @staticmethod
    def _click_first_node(page: Page) -> None:
        """Click the first non-parameter graph node to open the detail panel."""
        # Prefer a non-Parameter node so the detail panel has interesting content.
        nodes = page.locator(".node-group")
        count = nodes.count()
        for index in range(count):
            node = nodes.nth(index)
            label = node.locator(".node-class").text_content() or ""
            if label not in ("Parameter",):
                node.click()
                page.wait_for_selector("#knot-detail.visible", timeout=5_000)
                time.sleep(0.3)
                return
        # Fallback: click whatever is first.
        nodes.first.click()
        page.wait_for_selector("#knot-detail.visible", timeout=5_000)
        time.sleep(0.3)

    @staticmethod
    def _drill_into_sub_tapestry(page: Page) -> None:
        """Find a run with child_run_ids in RUNS_BY_ID, select it, then drillIn()."""
        result = page.evaluate("""() => {
            // Find any run that has a non-empty child_run_ids map.
            for (const run of Object.values(RUNS_BY_ID)) {
                if (run.child_run_ids && Object.keys(run.child_run_ids).length > 0) {
                    const nodeId = Object.keys(run.child_run_ids)[0];
                    // Make sure there's a tapestry that contains this node.
                    const tapestry = TAPESTRIES.find(t => t.nodes.some(n => n.is_sub_tapestry));
                    if (!tapestry) continue;
                    // Set state directly and render.
                    current = tapestry;
                    selectedRun = run;
                    renderGraph();
                    updateRunBar();
                    return nodeId;
                }
            }
            return null;
        }""")
        if not result:
            raise RuntimeError("No run with child_run_ids found in RUNS_BY_ID")
        time.sleep(0.4)
        page.evaluate(f"drillIn({result!r}, 0)")
        CaptureScreenshots._wait_for_graph(page)

    @staticmethod
    def _save(page: Page, name: str) -> None:
        dest = CaptureScreenshots._out_dir / f"{name}.png"
        page.screenshot(path=str(dest), full_page=False)
        print(f"  saved {dest.relative_to(CaptureScreenshots._repo)}")

    # -- screenshot definitions ---------------------------------------------

    @staticmethod
    def capture_all(page: Page, base_url: str) -> None:
        """Capture every screenshot referenced by docs/guides/visualization.md."""
        page.set_viewport_size(CaptureScreenshots._viewport)

        # explorer-overview  — first load, sidebar + graph visible
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._close_history(page)
        CaptureScreenshots._save(page, "explorer-overview")

        # explorer-pipeline-llm-agent  — chatbot_pipeline selected
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "chatbot_pipeline")
        CaptureScreenshots._close_history(page)
        CaptureScreenshots._save(page, "explorer-pipeline-llm-agent")

        # explorer-pipeline-complex-analytics
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "complex_analytics")
        CaptureScreenshots._close_history(page)
        CaptureScreenshots._save(page, "explorer-pipeline-complex-analytics")

        # explorer-horizontal-layout  — complex_analytics in horizontal mode
        page.click("#btn-horizontal")
        time.sleep(0.4)
        CaptureScreenshots._save(page, "explorer-horizontal-layout")
        page.click("#btn-vertical")  # reset

        # explorer-graph  — ci_pipeline (cleaner graph shape)
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "ci_pipeline")
        CaptureScreenshots._close_history(page)
        CaptureScreenshots._save(page, "explorer-graph")

        # explorer-pipeline-ci
        CaptureScreenshots._save(page, "explorer-pipeline-ci")

        # explorer-pipeline-content-moderation
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "content_moderation")
        CaptureScreenshots._close_history(page)
        CaptureScreenshots._save(page, "explorer-pipeline-content-moderation")

        # explorer-pipeline-sub-tapestry  — sub_tapestry pipeline
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "sub_tapestry")
        CaptureScreenshots._close_history(page)
        CaptureScreenshots._save(page, "explorer-pipeline-sub-tapestry")

        # explorer-knot-detail  — content_moderation with run overlay + detail panel
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "content_moderation")
        CaptureScreenshots._select_first_run(page)
        CaptureScreenshots._close_history(page)  # close history so graph has full width
        CaptureScreenshots._click_first_node(page)
        CaptureScreenshots._save(page, "explorer-knot-detail")

        # explorer-sub-tapestry-drilled  — drilled into validate SubTapestry
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "sub_tapestry")
        CaptureScreenshots._drill_into_sub_tapestry(page)
        CaptureScreenshots._save(page, "explorer-sub-tapestry-drilled")

        # explorer-history  — history panel open alongside the graph, run selected
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "content_moderation")
        CaptureScreenshots._select_first_run(page)
        CaptureScreenshots._save(page, "explorer-history")

        # explorer-history-panel  — same but with the LLM agent pipeline
        #                           (more runs, richer history list)
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "chatbot_pipeline")
        CaptureScreenshots._select_first_run(page)
        CaptureScreenshots._save(page, "explorer-history-panel")

        # explorer-dark-mode  — default (already dark)
        page.goto(base_url, wait_until="networkidle")
        CaptureScreenshots._wait_for_graph(page)
        CaptureScreenshots._select_pipeline(page, "chatbot_pipeline")
        # Ensure dark mode
        theme = page.evaluate("document.documentElement.dataset.theme || 'dark'")
        if theme == "light":
            page.click("#btn-theme")
            time.sleep(0.2)
        CaptureScreenshots._save(page, "explorer-dark-mode")

        # explorer-light-mode
        page.click("#btn-theme")
        time.sleep(0.2)
        CaptureScreenshots._save(page, "explorer-light-mode")
        # Reset to dark
        page.click("#btn-theme")

    # -- entry point --------------------------------------------------------

    @staticmethod
    def main() -> None:
        """Serve examples/, drive the Explorer, and write every PNG."""
        out_dir = CaptureScreenshots._out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        port, _ = CaptureScreenshots._start_server(CaptureScreenshots._examples_dir)
        base_url = f"http://127.0.0.1:{port}/pirn_explorer.html"
        print(f"Serving {CaptureScreenshots._examples_dir} on {base_url}")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport=CaptureScreenshots._viewport)
            page = context.new_page()
            try:
                CaptureScreenshots.capture_all(page, base_url)
            finally:
                browser.close()

        count = len(list(out_dir.glob("*.png")))
        print(f"\nDone — {count} PNGs in {out_dir.relative_to(CaptureScreenshots._repo)}")


if __name__ == "__main__":
    CaptureScreenshots.main()
