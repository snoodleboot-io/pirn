"""``WriteFileTool`` — write a UTF-8 text file scoped to a bound root directory."""

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
from pirn_agents.tools.tool_permissions import ToolPermissions


class WriteFileTool(Tool):
    """Write UTF-8 text to a path relative to the tool's root directory."""

    tool_name: ClassVar[str] = "write_file"
    permissions: ClassVar[ToolPermissions] = ToolPermissions(mutating=True)

    def __init__(
        self,
        *,
        path: Knot | str,
        content: Knot | str,
        root: Knot | str | Path,
        max_bytes: Knot | int = 1_000_000,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            path=path, content=content, root=root, max_bytes=max_bytes, _config=_config, **kwargs
        )

    async def process(
        self,
        path: Annotated[str, Field(description="File path relative to the tool's root directory.")],
        content: Annotated[str, Field(description="The UTF-8 text to write.")],
        root: str | Path,
        max_bytes: int = 1_000_000,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Write ``content`` to the requested path and return the byte count.

        Args:
            path: The file to write, relative to ``root``.
            content: The text to write.
            root: The directory every write is confined to; bound once with
                ``WriteFileTool.bind(root=...)``.
            max_bytes: Maximum number of UTF-8 bytes accepted for ``content``.

        Returns:
            ``{"path", "bytes_written"}``.

        Raises:
            ValueError: If ``max_bytes`` is not positive, the path is empty or
                escapes the root, the parent does not exist, or ``content``
                exceeds ``max_bytes``.
        """
        if max_bytes <= 0:
            raise ValueError(f"write_file: max_bytes must be positive, got {max_bytes}")
        if not path:
            raise ValueError("write_file: 'path' must be a non-empty string")
        encoded = content.encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError(
                f"write_file: content of {len(encoded)} bytes exceeds max_bytes {max_bytes}"
            )
        guard = PathGuard(root=str(root))
        resolved = guard.resolve(path, must_exist=False)
        await asyncio.to_thread(self._write, resolved, encoded)
        return {"path": path, "bytes_written": len(encoded)}

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        """Write ``data`` to ``path`` (overwriting), refusing to clobber a symlink."""
        if path.is_symlink():
            raise ValueError(f"write_file: refusing to overwrite symlink: {path.name!r}")
        with path.open("wb") as handle:
            handle.write(data)
