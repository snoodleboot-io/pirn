"""Shared regex compilation and matching utilities for agent guardrails.

Guards against ReDoS by enforcing a maximum pattern length before compilation,
and runs regex matches off the event loop via asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence

_MAX_PATTERN_LENGTH = 500


def compile_safe_pattern(
    raw: str,
    *,
    index: int,
    owner: str,
    field: str = "patterns",
    flags: int = 0,
) -> re.Pattern[str]:
    """Compile a user-supplied regex after validating it is within safe length bounds.

    Raises:
        ValueError: If the pattern exceeds _MAX_PATTERN_LENGTH characters or
            is not a valid regex.
    """
    if len(raw) > _MAX_PATTERN_LENGTH:
        raise ValueError(
            f"{owner}: {field}[{index}] exceeds maximum pattern length of "
            f"{_MAX_PATTERN_LENGTH} characters (got {len(raw)}). "
            "Long patterns risk catastrophic backtracking."
        )
    try:
        return re.compile(raw, flags=flags)
    except re.error as exc:
        raise ValueError(
            f"{owner}: {field}[{index}] is not a valid regex: {exc}"
        ) from exc


async def search_any(
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
