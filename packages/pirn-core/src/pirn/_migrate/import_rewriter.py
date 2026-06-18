"""Line-based rewriter for the ``pirn.domains.<x>`` -> ``pirn_<x>`` split.

See :mod:`pirn._migrate` for background. The rewriter is a pure text
transform: it operates line by line on ``.py`` source, only ever touching
``import`` / ``from ... import`` statements that reference one of the six
known domains, and otherwise preserves formatting, indentation and comments
byte-for-byte. It is idempotent (a rewritten file is a fixed point) and
deterministic (identical input always yields identical output).
"""

from __future__ import annotations

import re
from pathlib import Path


class ImportRewriter:
    """Rewrites legacy ``pirn.domains.<x>`` imports to ``pirn_<x>``.

    The set of domains is fixed framework data (the monolith carved out
    exactly these six packages), so it is stored as a lowercase class
    attribute rather than a configurable constant. Only these names are
    ever rewritten; any other ``pirn.domains.<other>`` reference (e.g.
    ``pirn.domains.extras_loader``) is left untouched.
    """

    _domains: tuple[str, ...] = (
        "signal",
        "oilgas",
        "data",
        "ml",
        "agents",
        "health",
    )

    def __init__(self) -> None:
        domain_alt = "|".join(self._domains)
        # The captured domain is followed by one of: end-of-token (whitespace,
        # `.`, `,`, end-of-line) — never another identifier character — so a
        # non-domain like `pirn.domains.datasource` cannot match `data`.
        boundary = r"(?![A-Za-z0-9_])"

        # `from pirn.domains import <x>[ as alias]` -> `import pirn_<x>[ as alias]`.
        # Only handled when the imported name is a single bare domain.
        self._from_domains_import = re.compile(
            rf"^(?P<indent>\s*)from\s+pirn\.domains\s+import\s+"
            rf"(?P<domain>{domain_alt}){boundary}"
            rf"(?P<alias>\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?\s*$"
        )

        # `from pirn.domains.<x>[.sub...] import ...` -> `from pirn_<x>[.sub...] import ...`.
        self._from_submodule = re.compile(
            rf"^(?P<indent>\s*)from\s+pirn\.domains\."
            rf"(?P<domain>{domain_alt}){boundary}"
            rf"(?P<tail>(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s+import\s"
        )

        # `import pirn.domains.<x>[.sub...][ as alias]` -> `import pirn_<x>[.sub...][ as alias]`.
        self._import_module = re.compile(
            rf"^(?P<indent>\s*)import\s+pirn\.domains\."
            rf"(?P<domain>{domain_alt}){boundary}"
            rf"(?P<tail>(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
            rf"(?P<rest>\s+as\s+[A-Za-z_][A-Za-z0-9_]*\s*|\s*)$"
        )

    def rewrite_line(self, line: str) -> str:
        """Rewrite a single source line, returning it unchanged if no rule applies."""
        match = self._from_domains_import.match(line)
        if match is not None:
            alias = match.group("alias") or ""
            return f"{match.group('indent')}import pirn_{match.group('domain')}{alias}\n"

        match = self._from_submodule.match(line)
        if match is not None:
            end = match.end()
            head = (
                f"{match.group('indent')}from pirn_{match.group('domain')}"
                f"{match.group('tail')} import "
            )
            return head + line[end:]

        match = self._import_module.match(line)
        if match is not None:
            return (
                f"{match.group('indent')}import pirn_{match.group('domain')}"
                f"{match.group('tail')}{match.group('rest')}"
            )

        return line

    def rewrite_text(self, source: str) -> str:
        """Rewrite every applicable import line in a source string."""
        if "pirn.domains." not in source and "pirn.domains " not in source:
            return source
        lines = source.splitlines(keepends=True)
        return "".join(self.rewrite_line(line) for line in lines)

    def rewrite_file(self, path: Path) -> bool:
        """Rewrite a file in place. Returns ``True`` iff its contents changed."""
        original = path.read_text(encoding="utf-8")
        rewritten = self.rewrite_text(original)
        if rewritten == original:
            return False
        path.write_text(rewritten, encoding="utf-8")
        return True

    def file_needs_rewrite(self, path: Path) -> bool:
        """Return ``True`` iff the file would change, without writing it."""
        original = path.read_text(encoding="utf-8")
        return self.rewrite_text(original) != original
