"""CLI entry point for ``pirn-explore``."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pirn-explore",
        description="Render all pirn pipelines in a folder as an interactive D3 explorer.",
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="Folder to scan for pipelines (default: current directory)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        metavar="FILE",
        help="Output HTML file (default: pirn_explorer.html in the folder)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser automatically",
    )
    args = parser.parse_args(argv)

    folder = Path(args.folder).resolve()
    if not folder.is_dir():
        print(f"pirn-explore: {folder} is not a directory", file=sys.stderr)
        return 1

    output = Path(args.output) if args.output else folder / "pirn_explorer.html"

    from pirn.viz.explorer import generate_explorer_html

    html = generate_explorer_html(folder)
    output.write_text(html, encoding="utf-8")
    print(f"pirn-explore: wrote {output}")

    if not args.no_open:
        webbrowser.open(output.as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
