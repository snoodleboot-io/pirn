"""``GlobTool`` — match files by glob pattern, scoped to an injected root."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.filesystem._path_guard import PathGuard


class GlobTool(BaseTool):
    """Glob for files under the configured root, never returning paths outside it."""

    def __init__(self, *, root: str | Path, max_results: int = 1000) -> None:
        """Bind the tool to a root directory and a result-count cap.

        Args:
            root: The directory the glob is confined to.
            max_results: Maximum number of matches returned; extra matches are
                dropped and the result is flagged truncated.

        Raises:
            ValueError: If ``root`` is not an existing directory or ``max_results``
                is not positive.
        """
        if max_results <= 0:
            raise ValueError(f"glob: max_results must be positive, got {max_results}")
        self._guard = PathGuard(root=str(root))
        self._max_results = max_results

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"glob"``."""
        return "glob"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Find files matching a glob pattern (e.g. '**/*.py') under the root directory."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``pattern`` argument."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "A glob pattern relative to the root, e.g. '**/*.txt'.",
                }
            },
            "required": ["pattern"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return root-relative paths matching ``pattern``, capped at ``max_results``.

        Returns:
            ``{"pattern", "matches": [str...], "count", "truncated"}`` — matches are
            relative to the root and never escape it.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If the pattern is missing, absolute, or contains ``..``.
        """
        self._require_mapping(self.name, arguments)
        pattern = self._string_argument(self.name, arguments, "pattern")
        if Path(pattern).is_absolute():
            raise ValueError(f"glob: refusing absolute pattern {pattern!r}")
        if ".." in Path(pattern).parts:
            raise ValueError(f"glob: refusing '..' in pattern {pattern!r}")
        matches = await asyncio.to_thread(self._glob, pattern)
        truncated = len(matches) > self._max_results
        return {
            "pattern": pattern,
            "matches": matches[: self._max_results],
            "count": len(matches),
            "truncated": truncated,
        }

    def _glob(self, pattern: str) -> list[str]:
        """Return sorted, in-root, root-relative matches for ``pattern``."""
        results: list[str] = []
        for match in self._guard.root.glob(pattern):
            resolved = match.resolve()
            if resolved.is_relative_to(self._guard.root) and not match.is_symlink():
                results.append(match.relative_to(self._guard.root).as_posix())
        return sorted(results)
