"""``ScanTarget`` — one file the convention gate checks, with the facts that decide how."""

from __future__ import annotations

from pathlib import Path

from gatekit.source_file import SourceFile


class ScanTarget:
    """A parsed file plus the package it is reported under and whether it is test code.

    ``package`` is the distribution directory for anything under ``packages/`` (so
    ``packages/pirn-core/pirn/core/knot.py`` is reported under ``pirn-core``) and the
    first path segment otherwise (``examples``, ``scripts``).

    ``is_test_code`` is true for anything under a ``tests`` directory and for every
    ``conftest.py``. Test code is held to the rules that are about *meaning* —
    suppressions, deprecation, aliases, knot design — and not (yet) to the structural
    rules about file layout; see ``CheckConventions``' module docstring.
    """

    __slots__ = ("is_test_code", "package", "relative_posix", "source_file")

    def __init__(self, source_file: SourceFile, repository_root: Path) -> None:
        self.source_file = source_file
        path = source_file.path
        relative = path.resolve().relative_to(repository_root.resolve())
        self.relative_posix = relative.as_posix()
        parts = relative.parts
        if len(parts) > 1 and parts[0] == "packages":
            self.package = parts[1]
        else:
            self.package = parts[0] if parts else "."
        self.is_test_code = "tests" in parts or path.name == "conftest.py"

    @property
    def path(self) -> Path:
        return self.source_file.path
