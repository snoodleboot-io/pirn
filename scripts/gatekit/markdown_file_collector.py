"""Expand command-line paths into the markdown documentation files to check."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar


class MarkdownFileCollector:
    """Turn file and directory arguments into a sorted list of ``*.md`` files.

    Directories are walked recursively, skipping build/tooling directories and
    ``CHANGELOG.md`` (its entries describe past removals by their old names).
    Raises ``ValueError`` when the invocation cannot check anything.
    """

    _skipped_dirs: ClassVar[frozenset[str]] = frozenset(
        {".venv", "node_modules", "site", "__pycache__", ".git"}
    )
    _skipped_files: ClassVar[frozenset[str]] = frozenset({"CHANGELOG.md"})

    @classmethod
    def collect(cls, arguments: list[str]) -> list[Path]:
        """Every markdown file named by, or found under, ``arguments``."""
        if not arguments:
            raise ValueError("no paths given")
        found: set[Path] = set()
        for argument in arguments:
            path = Path(argument)
            if not path.exists():
                raise ValueError(f"path does not exist: {argument}")
            if path.is_dir():
                found.update(cls._walk(path))
            elif path.suffix == ".md" and path.name not in cls._skipped_files:
                found.add(path)
        if not found:
            raise ValueError(f"no markdown files found under: {' '.join(arguments)}")
        return sorted(found)

    @classmethod
    def _walk(cls, directory: Path) -> list[Path]:
        files: list[Path] = []
        for candidate in directory.rglob("*.md"):
            relative = candidate.relative_to(directory).parts[:-1]
            if cls._skipped_dirs.intersection(relative):
                continue
            if candidate.name in cls._skipped_files or not candidate.is_file():
                continue
            files.append(candidate)
        return files
