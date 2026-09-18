"""``ListDirTool`` — list a directory's entries, scoped to a bound root directory."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.filesystem.path_guard import PathGuard
from pirn_agents.tools.tool import Tool


class ListDirTool(Tool):
    """List entries of a directory relative to the tool's root directory."""

    tool_name: ClassVar[str] = "list_dir"

    def __init__(
        self,
        *,
        root: Knot | str | Path,
        path: Knot | str = "",
        max_entries: Knot | int = 1000,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(root=root, path=path, max_entries=max_entries, _config=_config, **kwargs)

    async def process(
        self,
        root: str | Path,
        path: Annotated[
            str, Field(description="Directory relative to the root ('' or omitted = root).")
        ] = "",
        max_entries: int = 1000,
        **_: Any,
    ) -> Mapping[str, Any]:
        """List the requested directory, capped at ``max_entries``.

        Args:
            root: The directory every listing is confined to; bound once with
                ``ListDirTool.bind(root=...)``.
            path: The directory to list, relative to ``root``.
            max_entries: Maximum number of entries returned; extra entries are
                dropped and the result is flagged truncated.

        Returns:
            ``{"path", "entries": [{"name", "type"}...], "count", "truncated"}``.

        Raises:
            ValueError: If ``max_entries`` is not positive, or the path escapes
                the root or is not a directory.
        """
        if max_entries <= 0:
            raise ValueError(f"list_dir: max_entries must be positive, got {max_entries}")
        guard = PathGuard(root=str(root))
        resolved = guard.resolve(path, must_exist=True)
        if not resolved.is_dir():
            raise ValueError(f"list_dir: not a directory: {path!r}")
        entries = await asyncio.to_thread(self._list, resolved)
        truncated = len(entries) > max_entries
        return {
            "path": path,
            "entries": entries[:max_entries],
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
