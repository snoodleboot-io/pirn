"""``FallbackResult`` — the typed outcome of a router + fallback-chain run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.tool_result import ToolResult


@dataclass(frozen=True)
class FallbackResult(PirnOpaqueValue):
    """Outcome of dispatching through a confidence-ordered fallback chain.

    Attributes
    ----------
    succeeded:
        Whether some candidate returned a successful :class:`ToolResult`.
    chosen:
        The name of the candidate that succeeded, or ``None`` on exhaustion.
    result:
        The successful :class:`ToolResult`, or ``None`` on exhaustion.
    attempted:
        Names of candidates actually invoked, in order.
    skipped:
        Names of candidates skipped because their confidence was below their
        ``min_confidence`` floor.
    """

    succeeded: bool
    chosen: str | None
    result: ToolResult | None
    attempted: tuple[str, ...]
    skipped: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "succeeded": self.succeeded,
            "chosen": self.chosen,
            "result": None if self.result is None else self.result._pirn_audit_dict(),
            "attempted": list(self.attempted),
            "skipped": list(self.skipped),
        }
