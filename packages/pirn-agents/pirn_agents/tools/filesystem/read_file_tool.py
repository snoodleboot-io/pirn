"""``ReadFileTool`` — read a UTF-8 text file scoped to an injected root."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.filesystem._path_guard import PathGuard


class ReadFileTool(BaseTool):
    """Read a text file, refusing any path that escapes the configured root."""

    def __init__(self, *, root: str | Path, max_bytes: int = 1_000_000) -> None:
        """Bind the tool to a root directory and a per-read size cap.

        Args:
            root: The directory every read is confined to.
            max_bytes: Maximum number of bytes read from a file; content beyond
                this is truncated and flagged.

        Raises:
            ValueError: If ``root`` is not an existing directory or ``max_bytes``
                is not positive.
        """
        if max_bytes <= 0:
            raise ValueError(f"read_file: max_bytes must be positive, got {max_bytes}")
        self._guard = PathGuard(root=str(root))
        self._max_bytes = max_bytes

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"read_file"``."""
        return "read_file"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Read a UTF-8 text file at a path relative to the tool's root directory."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``path`` argument."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the tool's root directory.",
                }
            },
            "required": ["path"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Read the requested file and return its (possibly truncated) content.

        Returns:
            ``{"path", "content", "bytes", "truncated"}`` where ``truncated`` is
            ``True`` when the file exceeded ``max_bytes``.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If the path is missing, escapes the root, or is not a file.
        """
        self._require_mapping(self.name, arguments)
        relative = self._string_argument(self.name, arguments, "path")
        resolved = self._guard.resolve(relative, must_exist=True)
        if not resolved.is_file():
            raise ValueError(f"read_file: not a regular file: {relative!r}")
        data = await asyncio.to_thread(self._read_capped, resolved)
        size = resolved.stat().st_size
        truncated = len(data) > self._max_bytes
        content = data[: self._max_bytes].decode("utf-8", errors="replace")
        return {
            "path": relative,
            "content": content,
            "bytes": size,
            "truncated": truncated,
        }

    def _read_capped(self, path: Path) -> bytes:
        """Read up to ``max_bytes + 1`` bytes so truncation can be detected."""
        with path.open("rb") as handle:
            return handle.read(self._max_bytes + 1)
