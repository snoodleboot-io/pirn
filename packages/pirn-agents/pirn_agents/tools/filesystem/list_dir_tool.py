"""``ListDirTool`` — list a directory's entries, scoped to an injected root."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.filesystem._path_guard import PathGuard


class ListDirTool(BaseTool):
    """List directory entries, refusing any path that escapes the configured root."""

    def __init__(self, *, root: str | Path, max_entries: int = 1000) -> None:
        """Bind the tool to a root directory and an entry-count cap.

        Args:
            root: The directory every listing is confined to.
            max_entries: Maximum number of entries returned; extra entries are
                dropped and the result is flagged truncated.

        Raises:
            ValueError: If ``root`` is not an existing directory or ``max_entries``
                is not positive.
        """
        if max_entries <= 0:
            raise ValueError(f"list_dir: max_entries must be positive, got {max_entries}")
        self._guard = PathGuard(root=str(root))
        self._max_entries = max_entries

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"list_dir"``."""
        return "list_dir"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "List entries of a directory relative to the tool's root directory."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the optional ``path`` argument."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory relative to the root ('' or omitted = root).",
                }
            },
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """List the requested directory, capped at ``max_entries``.

        Returns:
            ``{"path", "entries": [{"name", "type"}...], "count", "truncated"}``.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If the path escapes the root or is not a directory.
        """
        self._require_mapping(self.name, arguments)
        raw = arguments.get("path", arguments.get("input", ""))
        relative = raw if isinstance(raw, str) else ""
        resolved = self._guard.resolve(relative, must_exist=True)
        if not resolved.is_dir():
            raise ValueError(f"list_dir: not a directory: {relative!r}")
        entries = await asyncio.to_thread(self._list, resolved)
        truncated = len(entries) > self._max_entries
        return {
            "path": relative,
            "entries": entries[: self._max_entries],
            "count": len(entries),
            "truncated": truncated,
        }

    @staticmethod
    def _list(directory: Path) -> list[dict[str, str]]:
        """Return sorted ``{name, type}`` records for a directory's children."""
        records: list[dict[str, str]] = []
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            if child.is_symlink():
                kind = "symlink"
            elif child.is_dir():
                kind = "dir"
            elif child.is_file():
                kind = "file"
            else:
                kind = "other"
            records.append({"name": child.name, "type": kind})
        return records
