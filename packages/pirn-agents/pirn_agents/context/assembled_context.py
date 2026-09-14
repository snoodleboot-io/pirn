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

    @staticmethod
    def _audit_all(values: tuple[PirnOpaqueValue, ...]) -> list[Any]:
        """Audit each child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return [value._pirn_audit_dict() for value in values]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "kept": self._audit_all(self.kept),
            "evicted": self._audit_all(self.evicted),
            "total_tokens": self.total_tokens,
        }
