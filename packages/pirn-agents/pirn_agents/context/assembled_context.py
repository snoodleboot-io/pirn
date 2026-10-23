"""``AssembledContext`` — the result of a token-budgeted assembly pass.

ADR agents-speaks-core WS6b: a value crossing a knot boundary is a
``Payload[Frame, Data]``. PIR-868 rebased the specialization results onto that
split and PIR-874 does the same here. The split: ``data`` is what the pass
produced (the kept items); the frame
(:class:`~pirn_agents.context.assembled_context_frame.AssembledContextFrame`)
is a fact about the run (what was evicted, the kept token total).

``context/`` must not import from ``specializations/``, so this subclasses
:class:`pirn.core.payload.Payload` directly and adds the same structural
``__eq__`` that ``AgentResult`` carries.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.assembled_context_frame import AssembledContextFrame
from pirn_agents.context.context_item import ContextItem


class AssembledContext(Payload[AssembledContextFrame, tuple[ContextItem, ...]]):
    """The outcome of fitting context items under a token budget.

    ``data`` is the kept items in their original order; ``metadata`` is the
    :class:`AssembledContextFrame` (``evicted``, ``total_tokens``). The
    constructor takes ``kept``, ``evicted`` and ``total_tokens`` by name.
    """

    def __init__(
        self,
        *,
        kept: Sequence[ContextItem],
        evicted: Sequence[ContextItem],
        total_tokens: int,
    ) -> None:
        frame = AssembledContextFrame(total_tokens=total_tokens, evicted=tuple(evicted))
        super().__init__(metadata=frame, data=tuple(kept))

    @staticmethod
    def _audit_all(values: tuple[PirnOpaqueValue, ...]) -> list[Any]:
        """Audit each child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return [value._pirn_audit_dict() for value in values]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["kept"] = self._audit_all(self.data)
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
