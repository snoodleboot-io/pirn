"""``AssembledContext`` — the result of a token-budgeted assembly pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.context_item import ContextItem


@dataclass(frozen=True)
class AssembledContext(PirnOpaqueValue):
    """The outcome of fitting context items under a token budget.

    Attributes
    ----------
    kept:
        Items retained, in their original order.
    evicted:
        Items dropped to fit the budget, in the order they were evicted.
    total_tokens:
        Total token cost of the ``kept`` items.
    """

    kept: tuple[ContextItem, ...]
    evicted: tuple[ContextItem, ...]
    total_tokens: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "kept": [item._pirn_audit_dict() for item in self.kept],
            "evicted": [item._pirn_audit_dict() for item in self.evicted],
            "total_tokens": self.total_tokens,
        }
