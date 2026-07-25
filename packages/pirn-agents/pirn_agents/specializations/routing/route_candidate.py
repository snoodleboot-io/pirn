"""``RouteCandidate`` — a typed routing target with a confidence floor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tool import Tool


@dataclass(frozen=True)
class RouteCandidate(PirnOpaqueValue):
    """One typed candidate the router may dispatch to.

    Attributes
    ----------
    name:
        Stable identifier used to look this candidate's confidence up and to
        report which candidate handled (or was skipped for) a request.
    tool:
        The :class:`Tool` invoked when this candidate is chosen.
    min_confidence:
        The minimum confidence (0.0-1.0) this candidate requires before the
        fallback chain will invoke it; below it the chain skips to the next.
    """

    name: str
    tool: Tool
    min_confidence: float = 0.0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tool": self.tool.name,
            "min_confidence": self.min_confidence,
        }
