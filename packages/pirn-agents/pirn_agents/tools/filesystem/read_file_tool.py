"""``ReadFileTool`` — read a UTF-8 text file scoped to a bound root directory."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.filesystem._path_guard import PathGuard
from pirn_agents.tools.tool import Tool


class ReadFileTool(Tool):
    """Read a UTF-8 text file at a path relative to the tool's root directory."""

    tool_name: ClassVar[str] = "read_file"

    def __init__(
        self,
        *,
        path: Knot | str,
        root: Knot | str | Path,
        max_bytes: Knot | int = 1_000_000,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(path=path, root=root, max_bytes=max_bytes, _config=_config, **kwargs)

    async def process(
        self,
        path: Annotated[str, Field(description="File path relative to the tool's root directory.")],
        root: str | Path,
        max_bytes: int = 1_000_000,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Read the requested file and return its (possibly truncated) content.

        Args:
            path: The file to read, relative to ``root``.
            root: The directory every read is confined to; bound once with
                ``ReadFileTool.bind(root=...)``.
            max_bytes: Maximum number of bytes read; content beyond this is
                truncated and flagged.

        Returns:
            ``{"path", "content", "bytes", "truncated"}`` where ``truncated`` is
            ``True`` when the file exceeded ``max_bytes``.

        Raises:
            ValueError: If ``max_bytes`` is not positive, ``root`` is not an
                existing directory, or the path is empty, escapes the root, or
                is not a file.
        """
        if max_bytes <= 0:
            raise ValueError(f"read_file: max_bytes must be positive, got {max_bytes}")
        if not path:
            raise ValueError("read_file: 'path' must be a non-empty string")
        guard = PathGuard(root=str(root))
        resolved = guard.resolve(path, must_exist=True)
        if not resolved.is_file():
            raise ValueError(f"read_file: not a regular file: {path!r}")
        data = await asyncio.to_thread(self._read_capped, resolved, max_bytes)
        size = resolved.stat().st_size
        truncated = len(data) > max_bytes
        content = data[:max_bytes].decode("utf-8", errors="replace")
        return {"path": path, "content": content, "bytes": size, "truncated": truncated}

    @staticmethod
    def _read_capped(path: Path, max_bytes: int) -> bytes:
        """Read up to ``max_bytes + 1`` bytes so truncation can be detected."""
        with path.open("rb") as handle:
            return handle.read(max_bytes + 1)
