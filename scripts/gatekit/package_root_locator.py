"""``PackageRootLocator`` — find the ``packages/<dist>/`` directory a path lives under."""

from __future__ import annotations

from pathlib import Path


class PackageRootLocator:
    """Locate the workspace distribution directory that owns a file path."""

    @staticmethod
    def locate(path: Path) -> Path | None:
        """The ``packages/<dist>/`` directory *path* lives under, or ``None``."""
        parts = path.resolve().parts
        for index, part in enumerate(parts):
            if part == "packages" and index + 1 < len(parts):
                return Path(*parts[: index + 2])
        return None
