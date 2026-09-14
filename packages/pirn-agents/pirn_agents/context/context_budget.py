"""``ContextBudget`` — a token budget with optional reserved headroom."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ContextBudget(PirnOpaqueValue):
    """A token budget for context assembly.

    Attributes
    ----------
    max_tokens:
        The hard ceiling on total context tokens.
    reserved_tokens:
        Tokens held back from ``max_tokens`` (e.g. for the model's response or
        a system prompt not part of the assembled items). :meth:`available`
        returns the room actually usable by items.
    """

    max_tokens: int
    reserved_tokens: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.max_tokens, int) or self.max_tokens < 0:
            raise ValueError(
                f"ContextBudget: max_tokens must be a non-negative int, got {self.max_tokens!r}"
            )
        if not isinstance(self.reserved_tokens, int) or self.reserved_tokens < 0:
            raise ValueError(
                "ContextBudget: reserved_tokens must be a non-negative int, "
                f"got {self.reserved_tokens!r}"
            )
        if self.reserved_tokens > self.max_tokens:
            raise ValueError("ContextBudget: reserved_tokens must not exceed max_tokens")

    def available(self) -> int:
        """Return the token room usable by items (``max - reserved``)."""
        return self.max_tokens - self.reserved_tokens

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"max_tokens": self.max_tokens, "reserved_tokens": self.reserved_tokens}
