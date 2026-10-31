"""``CompactionResult`` — the outcome of a compaction pass.

ADR agents-speaks-core WS6b: a value crossing a knot boundary is a
``Payload[Frame, Data]``. PIR-868 rebased the specialization results onto that
split and PIR-874 does the same here. The split: ``data`` is what the pass
produced (the retained items); the frame
(:class:`~pirn_agents.context.compaction_frame.CompactionFrame`) is a fact
about the run (whether it triggered, the token counts, the summary and what
was evicted).

``context/`` must not import from ``specializations/``, so this subclasses
:class:`pirn.core.payload.Payload` directly and adds the same structural
``__eq__`` that ``AgentResult`` carries.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.compaction_frame import CompactionFrame
from pirn_agents.context.context_item import ContextItem


class CompactionResult(Payload[CompactionFrame, tuple[ContextItem, ...]]):
    """The result of compacting context.

    ``data`` is the post-compaction items in order: preserved (incl. pinned)
    content with a single summary item standing in for the compacted block.
    ``metadata`` is the :class:`CompactionFrame`. The constructor takes
    ``retained``, ``evicted``, ``summary``, ``summary_item``, ``triggered``,
    ``tokens_before`` and ``tokens_after`` by name.
    """

    def __init__(
        self,
        *,
        retained: Sequence[ContextItem],
        evicted: Sequence[ContextItem],
        summary: str,
        summary_item: ContextItem | None,
        triggered: bool,
        tokens_before: int,
        tokens_after: int,
    ) -> None:
        frame = CompactionFrame(
            triggered=triggered,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            summary=summary,
            summary_item=summary_item,
            evicted=tuple(evicted),
        )
        super().__init__(metadata=frame, data=tuple(retained))

    @staticmethod
    def _audit_all(values: tuple[PirnOpaqueValue, ...]) -> list[Any]:
        """Audit each child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return [value._pirn_audit_dict() for value in values]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["retained"] = self._audit_all(self.data)
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
