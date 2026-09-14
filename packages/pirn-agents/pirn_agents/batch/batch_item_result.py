"""``BatchItemResult`` — the isolated outcome of one item in a batch run.

The outcome *is* core's ``Ok | Err | Skipped`` ``Result`` (ADR agents-speaks-core
WS2, PIR-872): an item that ran to completion is ``Ok``, one that raised — or
outlived its ``KnotConfig.timeout`` (``Err`` carrying ``KnotTimeoutError``) — is
``Err``, and one already completed in a prior run is ``Skipped(reason="resumed")``.
There is no parallel status enum; the batch-specific distinctions are read off
the ``Result`` variant and the error type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents._internal.json_shape import JsonShape


@dataclass(frozen=True)
class BatchItemResult(PirnOpaqueValue):
    """The terminal outcome of running the agent over a single input item.

    A frozen value carrying everything a streaming sink or per-fire summary
    needs. The per-item agent's return value is opaque, so this wraps
    :class:`PirnOpaqueValue` to stay opaque at pirn IO boundaries.

    Attributes
    ----------
    index:
        Position of the item in the input stream (0-based). Non-negative.
    key:
        Stable identity of the item — the suffix of its knot id, and so its
        resume key in ``RunHistory``.
    outcome:
        The item's core ``Result``: ``Ok(value=output)``, ``Err(record=...)``
        (the full :class:`ExceptionRecord` — type, message, detached
        traceback), or ``Skipped``.
    attempts:
        How many times the item was attempted (1 = succeeded first try).
    latency:
        Wall-clock seconds spent on the item (queue wait excluded).
    """

    #: :attr:`~pirn.managers.exception_record.ExceptionRecord.exc_type` values
    #: :attr:`timed_out` reads as a timeout. ``Result`` has no timeout variant,
    #: so a timeout is an ``Err`` whose error type names one.
    _timeout_exc_types: ClassVar[frozenset[str]] = frozenset({"TimeoutError", "KnotTimeoutError"})

    index: int
    key: str
    outcome: Result[Any]
    attempts: int = 1
    latency: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise ValueError(
                f"BatchItemResult: index must be a non-negative int, got {self.index!r}"
            )
        if not isinstance(self.key, str) or not self.key:
            raise TypeError("BatchItemResult: key must be a non-empty str")
        if not isinstance(self.outcome, (Ok, Err, Skipped)):
            raise TypeError(
                f"BatchItemResult: outcome must be Ok, Err, or Skipped, "
                f"got {type(self.outcome).__name__}"
            )

    @property
    def succeeded(self) -> bool:
        """Whether the item completed successfully (its outcome is ``Ok``)."""
        return isinstance(self.outcome, Ok)

    @property
    def output(self) -> Any:
        """The agent's return value for an ``Ok`` outcome; otherwise ``None``."""
        return self.outcome.value if isinstance(self.outcome, Ok) else None

    @property
    def exception(self) -> ExceptionRecord | None:
        """The captured failure record for an ``Err`` outcome; otherwise ``None``."""
        return self.outcome.record if isinstance(self.outcome, Err) else None

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
            "index": self.index,
            "key": self.key,
            "outcome": self._outcome_token(self.outcome),
            "output": self._json_safe(self.output),
            "error": self.error,
            "exception": None if self.exception is None else self.exception.model_dump(mode="json"),
            "skip_reason": self.outcome.reason if isinstance(self.outcome, Skipped) else None,
            "attempts": self.attempts,
            "latency": self.latency,
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
