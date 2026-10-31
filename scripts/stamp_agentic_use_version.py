#!/usr/bin/env python3
"""Pre-commit hook: keep the major-version stamp current in every AGENTIC_USE.md.

Reads MAJOR from the MAJOR_VERSION env var (CI) or falls back to the major
component of the version field in pyproject.toml. Rewrites the footer line
in every AGENTIC_USE.md under the repo root and exits 1 if any file changed
so pre-commit blocks the commit and prompts the author to re-stage.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import ClassVar


class StampAgenticUseVersion:
    """Rewrite the ``Covers pirn <major>.x`` footer of every ``AGENTIC_USE.md``."""

    _footer_re: ClassVar[re.Pattern[str]] = re.compile(
        r"(\*Generated for agent use\. Covers pirn )\d+(\.x\*)",
    )
    _pyproject_re: ClassVar[re.Pattern[str]] = re.compile(r'^version\s*=\s*"(\d+)\.')

    @staticmethod
    def _major_from_env() -> int | None:
        raw = os.environ.get("MAJOR_VERSION", "").strip()
        if raw.isdigit():
            return int(raw)
        return None

    @staticmethod
    def _major_from_pyproject(root: Path) -> int:
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            return 0
        for line in pyproject.read_text().splitlines():
            match = StampAgenticUseVersion._pyproject_re.match(line)
            if match:
                return int(match.group(1))
        return 0

    @staticmethod
    def main() -> int:
        """Stamp every ``AGENTIC_USE.md``; return 1 if any file was rewritten."""
        root = Path(__file__).resolve().parents[1]
        from_env = StampAgenticUseVersion._major_from_env()
        major = (
            from_env if from_env is not None else StampAgenticUseVersion._major_from_pyproject(root)
        )

        changed: list[Path] = []
        for path in sorted(root.rglob("AGENTIC_USE.md")):
            text = path.read_text()
            new_text = StampAgenticUseVersion._footer_re.sub(rf"\g<1>{major}\g<2>", text)
            if new_text != text:
                path.write_text(new_text)
                changed.append(path)

        if changed:
            for path in changed:
                print(f"stamped: {path.relative_to(root)}", file=sys.stderr)
            print(
                "AGENTIC_USE.md version stamp updated — re-stage the files above and retry.",
                file=sys.stderr,
            )
            return 1

        return 0


if __name__ == "__main__":
    sys.exit(StampAgenticUseVersion.main())
