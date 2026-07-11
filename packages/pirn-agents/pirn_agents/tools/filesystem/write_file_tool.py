"""``WriteFileTool`` — write a UTF-8 text file scoped to an injected root."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.filesystem._path_guard import resolve_in_root, resolve_root


class WriteFileTool(BaseTool):
    """Write a text file, refusing any path that escapes the configured root."""

    def __init__(self, *, root: str | Path, max_bytes: int = 1_000_000) -> None:
        """Bind the tool to a root directory and a per-write size cap.

        Args:
            root: The directory every write is confined to.
            max_bytes: Maximum number of UTF-8 bytes accepted for ``content``.

        Raises:
            ValueError: If ``root`` is not an existing directory or ``max_bytes``
                is not positive.
        """
        if max_bytes <= 0:
            raise ValueError(f"write_file: max_bytes must be positive, got {max_bytes}")
        self._root = resolve_root(str(root))
        self._max_bytes = max_bytes

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"write_file"``."""
        return "write_file"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Write UTF-8 text to a path relative to the tool's root directory."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``path`` and ``content`` arguments."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the tool's root directory.",
                },
                "content": {
                    "type": "string",
                    "description": "The UTF-8 text to write.",
                },
            },
            "required": ["path", "content"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Write ``content`` to the requested path and return the byte count.

        Returns:
            ``{"path", "bytes_written"}``.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If the path is missing/escapes the root, the parent does
                not exist, ``content`` is not a string, or it exceeds ``max_bytes``.
        """
        self._require_mapping(self.name, arguments)
        relative = self._string_argument(self.name, arguments, "path")
        content = arguments.get("content")
        if not isinstance(content, str):
            raise ValueError(
                f"write_file: 'content' must be a string, got {type(content).__name__}"
            )
        encoded = content.encode("utf-8")
        if len(encoded) > self._max_bytes:
            raise ValueError(
                f"write_file: content of {len(encoded)} bytes exceeds max_bytes {self._max_bytes}"
            )
        resolved = resolve_in_root(self._root, relative, must_exist=False)
        await asyncio.to_thread(self._write, resolved, encoded)
        return {"path": relative, "bytes_written": len(encoded)}

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        """Write ``data`` to ``path`` (overwriting), refusing to clobber a symlink."""
        if path.is_symlink():
            raise ValueError(f"write_file: refusing to overwrite symlink: {path.name!r}")
        with path.open("wb") as handle:
            handle.write(data)
