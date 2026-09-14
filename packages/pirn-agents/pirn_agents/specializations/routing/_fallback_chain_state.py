"""``FallbackChainState`` — state threaded across fallback candidates."""

from __future__ import annotations

from dataclasses import dataclass

from pirn_agents.tools.tool_result import ToolResult


@dataclass
class FallbackChainState:
    """State threaded across fallback candidates."""

    attempted: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    succeeded_result: ToolResult | None = None
    chosen: str | None = None
    locked: bool = False
