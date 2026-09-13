"""``GlobTool`` — match files by glob pattern, scoped to a bound root directory."""

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


class GlobTool(Tool):
    """Find files matching a glob pattern (e.g. '**/*.py') under the root directory."""

    tool_name: ClassVar[str] = "glob"

    def __init__(
        self,
        *,
        pattern: Knot | str,
        root: Knot | str | Path,
        max_results: Knot | int = 1000,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pattern=pattern, root=root, max_results=max_results, _config=_config, **kwargs
        )

    async def process(
        self,
        pattern: Annotated[
            str, Field(description="A glob pattern relative to the root, e.g. '**/*.txt'.")
        ],
        root: str | Path,
        max_results: int = 1000,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Return root-relative paths matching ``pattern``, capped at ``max_results``.

        Args:
            pattern: The glob pattern, relative to ``root``.
            root: The directory the glob is confined to; bound once with
                ``GlobTool.bind(root=...)``.
            max_results: Maximum number of matches returned; extra matches are
                dropped and the result is flagged truncated.

        Returns:
            ``{"pattern", "matches": [str...], "count", "truncated"}`` — matches
            are relative to the root and never escape it.

        Raises:
            ValueError: If ``max_results`` is not positive, or the pattern is
                empty, absolute, or contains ``..``.
        """
        if max_results <= 0:
            raise ValueError(f"glob: max_results must be positive, got {max_results}")
        if not pattern:
            raise ValueError("glob: 'pattern' must be a non-empty string")
        if Path(pattern).is_absolute():
            raise ValueError(f"glob: refusing absolute pattern {pattern!r}")
        if ".." in Path(pattern).parts:
            raise ValueError(f"glob: refusing '..' in pattern {pattern!r}")
        guard = PathGuard(root=str(root))
        matches = await asyncio.to_thread(self._glob, guard, pattern)
        truncated = len(matches) > max_results
        return {
            "pattern": pattern,
            "matches": matches[:max_results],
            "count": len(matches),
            "truncated": truncated,
        }

    @staticmethod
    def _glob(guard: PathGuard, pattern: str) -> list[str]:
        """Return sorted, in-root, root-relative matches for ``pattern``."""
        results: list[str] = []
        for match in guard.root.glob(pattern):
            resolved = match.resolve()
            if resolved.is_relative_to(guard.root) and not match.is_symlink():
                results.append(match.relative_to(guard.root).as_posix())
        return sorted(results)
