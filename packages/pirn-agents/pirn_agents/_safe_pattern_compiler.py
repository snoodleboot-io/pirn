"""Shared regex compilation and matching utilities for agent guardrails.

Guards against ReDoS by enforcing a maximum pattern length before compilation,
and runs regex matches off the event loop via asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence


class SafePatternCompiler:
    """Compile and search user-supplied regexes with ReDoS length guards."""

    def __init__(self, *, max_pattern_length: int = 500) -> None:
        """Store the maximum permitted pattern length as instance state."""
        self._max_pattern_length = max_pattern_length

    @property
    def max_pattern_length(self) -> int:
        """The maximum permitted regex length (ReDoS guard threshold)."""
        return self._max_pattern_length

    def compile_safe_pattern(
        self,
        raw: str,
        *,
        index: int,
        owner: str,
        field: str = "patterns",
        flags: int = 0,
    ) -> re.Pattern[str]:
        """Compile a user-supplied regex after validating it is within safe length bounds.

        Raises:
            ValueError: If the pattern exceeds _max_pattern_length characters or
                is not a valid regex.
        """
        if len(raw) > self._max_pattern_length:
            raise ValueError(
                f"{owner}: {field}[{index}] exceeds maximum pattern length of "
                f"{self._max_pattern_length} characters (got {len(raw)}). "
                "Long patterns risk catastrophic backtracking."
            )
        try:
            return re.compile(raw, flags=flags)
        except re.error as exc:
            raise ValueError(f"{owner}: {field}[{index}] is not a valid regex: {exc}") from exc

    def compile_patterns(
        self,
        patterns: Sequence[str],
        *,
        owner: str,
        field: str,
        flags: int = 0,
    ) -> list[re.Pattern[str]]:
        """Validate and compile a non-empty sequence of regex pattern strings.

        Shared by the agent guardrail knots so the same checks run both at
        construction time (when patterns are supplied as a concrete sequence) and
        at process time (after a ``Knot`` reference resolves).

        Raises:
            TypeError: If ``patterns`` is not a sequence of strings.
            ValueError: If ``patterns`` is empty, or any entry is empty, invalid,
                or over-length (see :meth:`compile_safe_pattern`).
        """
        if not isinstance(patterns, Sequence) or isinstance(patterns, (str, bytes)):
            raise TypeError(f"{owner}: {field} must be a sequence of regex strings")
        if not patterns:
            raise ValueError(f"{owner}: {field} must be non-empty")
        compiled: list[re.Pattern[str]] = []
        for index, pattern in enumerate(patterns):
            if not isinstance(pattern, str) or not pattern:
                raise ValueError(
                    f"{owner}: {field}[{index}] must be a non-empty string, got {pattern!r}"
                )
            compiled.append(
                self.compile_safe_pattern(
                    pattern, index=index, owner=owner, field=field, flags=flags
                )
            )
        return compiled

    async def search_any(
        self,
        patterns: Sequence[re.Pattern[str]],
        content: str,
    ) -> re.Match[str] | None:
        """Return the first match of any pattern against content, running off the event loop."""

        def _search() -> re.Match[str] | None:
            for pattern in patterns:
                m = pattern.search(content)
                if m is not None:
                    return m
            return None

        return await asyncio.to_thread(_search)
