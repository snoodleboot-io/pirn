"""``AssembledContextFrame`` — run-level facts of a token-budgeted assembly pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.context_item import ContextItem


@dataclass(frozen=True)
class AssembledContextFrame(PirnOpaqueValue):
    """What an assembly pass did, as opposed to what it kept.

    The frame half of the ``Payload[AssembledContextFrame, tuple[ContextItem, ...]]``
    split (PIR-868, PIR-874).

    Attributes
    ----------
    total_tokens:
        Total token cost of the kept items.
    evicted:
        Items dropped to fit the budget, in the order they were evicted.
    """

    total_tokens: int
    evicted: tuple[ContextItem, ...]

    @staticmethod
    def _audit_all(values: tuple[PirnOpaqueValue, ...]) -> list[Any]:
        """Audit each child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return [value._pirn_audit_dict() for value in values]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "evicted": self._audit_all(self.evicted),
        }
