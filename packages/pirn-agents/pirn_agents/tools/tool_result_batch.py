"""``ToolResultBatch`` — the results an executed tool-call batch hands onward.

Counterpart of :class:`~pirn_agents.tools.tool_call_batch.ToolCallBatch`
(PIR-874; ADR agents-speaks-core WS6b). A *window* payload wrapping a tuple of
:class:`ToolResult`; the frame (:class:`ToolResultBatchFrame`) carries the
attempted/succeeded/failed split and the budgets the batch ran under. It
subclasses :class:`pirn.core.payload.Payload` directly because ``tools/`` must
not import from ``specializations/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.ok import Ok
from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_result_batch_frame import ToolResultBatchFrame


class ToolResultBatch(Payload[ToolResultBatchFrame, tuple[ToolResult, ...]]):
    """Ordered :class:`ToolResult` views plus their :class:`ToolResultBatchFrame`."""

    def __init__(
        self,
        results: Sequence[ToolResult],
        *,
        max_concurrency: int,
        timeout: float | None,
    ) -> None:
        data = tuple(results)
        succeeded = sum(1 for result in data if isinstance(result.outcome, Ok))
        frame = ToolResultBatchFrame(
            attempted=len(data),
            succeeded=succeeded,
            failed=len(data) - succeeded,
            max_concurrency=max_concurrency,
            timeout=timeout,
        )
        super().__init__(metadata=frame, data=data)

    @staticmethod
    def _audit_form(value: PirnOpaqueValue) -> Any:
        """Audit a nested value through the ``PirnOpaqueValue`` contract it shares with this one."""
        return value._pirn_audit_dict()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["results"] = [self._audit_form(result) for result in self.data]
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same type, equal frame and equal results."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data

    def __repr__(self) -> str:
        return f"{type(self).__name__}(results={self.data!r}, frame={self._metadata!r})"
