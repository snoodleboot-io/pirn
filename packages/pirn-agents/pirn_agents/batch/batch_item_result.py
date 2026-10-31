"""``BatchItemResult`` — the isolated outcome of one item in a batch run.

The outcome *is* core's ``Ok | Err | Skipped`` ``Result`` (ADR agents-speaks-core
WS2, PIR-872): an item that ran to completion is ``Ok``, one that raised — or
outlived its ``KnotConfig.timeout`` (``Err`` carrying ``KnotTimeoutError``) — is
``Err``, and one already completed in a prior run is ``Skipped(reason="resumed")``.
There is no parallel status enum; the batch-specific distinctions are read off
the ``Result`` variant and the error type.

ADR agents-speaks-core WS6b makes it a ``Payload[BatchItemFrame, Result[Any]]``
(PIR-868 pattern, PIR-874): the frame
(:class:`~pirn_agents.batch.batch_item_frame.BatchItemFrame`) carries
``index``/``key``/``attempts``/``latency`` and the data is the item's ``Result``.
The constructor still takes those fields by name; they are read back as
``metadata.<field>`` and ``data``. It subclasses ``Payload`` directly (not
``AgentResult``) because ``batch/`` sits outside ``specializations/`` and may not
import from it, so it adds the same structural ``__eq__`` ``AgentResult`` has.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.payload import Payload
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents._internal.json_shape import JsonShape
from pirn_agents.batch.batch_item_frame import BatchItemFrame


class BatchItemResult(Payload[BatchItemFrame, "Result[Any]"]):
    """The terminal outcome of running the agent over a single input item.

    A ``Payload`` carrying everything a streaming sink or per-fire summary
    needs; the per-item agent's return value is opaque, so it stays opaque at
    pirn IO boundaries.

    Read ``index``, ``key``, ``attempts`` and ``latency`` as ``metadata.<field>``
    and the item's core ``Result`` (``Ok(value=output)``, ``Err(record=...)``
    carrying the full :class:`ExceptionRecord`, or ``Skipped``) as ``data``.
    """

    #: :attr:`~pirn.managers.exception_record.ExceptionRecord.exc_type` values
    #: :attr:`timed_out` reads as a timeout. ``Result`` has no timeout variant,
    #: so a timeout is an ``Err`` whose error type names one.
    _timeout_exc_types: ClassVar[frozenset[str]] = frozenset({"TimeoutError", "KnotTimeoutError"})

    def __init__(
        self,
        index: int,
        key: str,
        outcome: Result[Any],
        attempts: int = 1,
        latency: float = 0.0,
    ) -> None:
        frame = BatchItemFrame(index=index, key=key, attempts=attempts, latency=latency)
        if not isinstance(outcome, (Ok, Err, Skipped)):
            raise TypeError(
                f"BatchItemResult: outcome must be Ok, Err, or Skipped, "
                f"got {type(outcome).__name__}"
            )
        super().__init__(metadata=frame, data=outcome)

    @property
    def succeeded(self) -> bool:
        """Whether the item completed successfully (its outcome is ``Ok``)."""
        return isinstance(self.data, Ok)

    @property
    def output(self) -> Any:
        """The agent's return value for an ``Ok`` outcome; otherwise ``None``."""
        return self.data.value if isinstance(self.data, Ok) else None

    @property
    def exception(self) -> ExceptionRecord | None:
        """The captured failure record for an ``Err`` outcome; otherwise ``None``."""
        return self.data.record if isinstance(self.data, Err) else None

    @property
    def error(self) -> str | None:
        """The failure message for an ``Err`` outcome; otherwise ``None``."""
        record = self.exception
        return None if record is None else record.message

    @property
    def timed_out(self) -> bool:
        """Whether the outcome is an ``Err`` whose error type is a timeout."""
        record = self.exception
        return record is not None and record.exc_type in self._timeout_exc_types

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this result.

        ``outcome`` is the ``Result`` variant's token (``"ok"``, ``"err"``,
        ``"skipped"``). ``output`` is stringified when it is not already a JSON
        primitive so the record stays serialisable without constraining what
        the agent may return.
        """
        return {
            **super()._pirn_audit_dict(),
            "outcome": self._outcome_token(self.data),
            "output": self._json_safe(self.output),
            "error": self.error,
            "exception": None if self.exception is None else self.exception.model_dump(mode="json"),
            "skip_reason": self.data.reason if isinstance(self.data, Skipped) else None,
        }

    @staticmethod
    def _outcome_token(outcome: Result[Any]) -> str:
        if isinstance(outcome, Ok):
            return "ok"
        if isinstance(outcome, Err):
            return "err"
        return "skipped"

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if JsonShape.is_any_mapping(value):
            return {str(k): BatchItemResult._json_safe(v) for k, v in value.items()}
        if JsonShape.is_list_or_tuple(value):
            return [BatchItemResult._json_safe(v) for v in value]
        return str(value)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()

    def __eq__(self, other: object) -> bool:
        """Structural equality: same type, equal frame and equal outcome."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data

    def __hash__(self) -> int:
        return hash((type(self), self.metadata.key))
