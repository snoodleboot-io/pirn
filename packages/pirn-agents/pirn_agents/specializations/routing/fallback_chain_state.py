"""``FallbackChainState`` — state threaded across fallback candidates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.tools.tool_result import ToolResult


@dataclass
class FallbackChainState:
    """State threaded across fallback candidates."""

    ordered: tuple[RouteCandidate, ...]
    arguments: Mapping[str, Any]
    confidences: Mapping[str, float]
    attempted: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    succeeded_result: ToolResult | None = None
    chosen: str | None = None
    locked: bool = False
