"""``ToolResultBatchFrame`` — run-level facts about an executed tool-call batch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ToolResultBatchFrame(PirnOpaqueValue):
    """Frame half of ``Payload[ToolResultBatchFrame, tuple[ToolResult, ...]]`` (PIR-874).

    Attributes
    ----------
    attempted:
        Number of calls the executor ran.
    succeeded:
        Number whose outcome is ``Ok``.
    failed:
        Number whose outcome is anything else (``Err`` or ``Skipped``).
    max_concurrency:
        The concurrency cap the batch ran under.
    timeout:
        The per-call time budget in seconds, or ``None`` when disabled.
    """

    attempted: int
    succeeded: int
    failed: int
    max_concurrency: int
    timeout: float | None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "max_concurrency": self.max_concurrency,
            "timeout": self.timeout,
        }
