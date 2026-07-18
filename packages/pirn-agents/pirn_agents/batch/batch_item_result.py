"""``BatchItemResult`` — the isolated outcome of one item in a batch run."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.batch.batch_item_status import BatchItemStatus


@dataclass(frozen=True)
class BatchItemResult(PirnOpaqueValue):
    """The terminal outcome of running the agent over a single input item.

    A frozen value (not a module constant) carrying everything a streaming sink,
    progress report, or checkpoint needs. ``output`` is opaque — it holds
    whatever the per-item agent callable returned — so this wraps
    :class:`PirnOpaqueValue` to stay opaque at pirn IO boundaries.

    Attributes
    ----------
    index:
        Position of the item in the input stream (0-based). Non-negative.
    key:
        Stable identity of the item, used for de-duplication on resume.
    status:
        Terminal :class:`BatchItemStatus`.
    output:
        The agent's return value when ``status`` is ``OK``; otherwise ``None``.
    error:
        Human-readable failure detail when ``status`` is ``ERROR``/``TIMEOUT``.
    attempts:
        How many times the item was attempted (1 = succeeded first try).
    latency:
        Wall-clock seconds spent on the item (queue wait excluded).
    """

    index: int
    key: str
    status: BatchItemStatus
    output: Any = None
    error: str | None = None
    attempts: int = 1
    latency: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise ValueError(
                f"BatchItemResult: index must be a non-negative int, got {self.index!r}"
            )
        if not isinstance(self.key, str) or not self.key:
            raise TypeError("BatchItemResult: key must be a non-empty str")
        if not isinstance(self.status, BatchItemStatus):
            raise TypeError(
                f"BatchItemResult: status must be a BatchItemStatus, got {type(self.status).__name__}"
            )

    @property
    def succeeded(self) -> bool:
        """Whether the item completed successfully."""
        return self.status is BatchItemStatus.OK

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this result.

        ``output`` is stringified when it is not already a JSON primitive so the
        record stays serialisable for a durable sink without constraining what
        the agent may return.
        """
        return {
            "index": self.index,
            "key": self.key,
            "status": self.status.value,
            "output": self._json_safe(self.output),
            "error": self.error,
            "attempts": self.attempts,
            "latency": self.latency,
        }

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Mapping):
            return {str(k): BatchItemResult._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [BatchItemResult._json_safe(v) for v in value]
        return str(value)

    @classmethod
    def from_payload(cls, payload: Any) -> BatchItemResult:
        """Reconstruct a result from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"BatchItemResult.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            index=int(payload["index"]),
            key=str(payload["key"]),
            status=BatchItemStatus(str(payload["status"])),
            output=payload.get("output"),
            error=payload.get("error"),
            attempts=int(payload.get("attempts", 1)),
            latency=float(payload.get("latency", 0.0)),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
