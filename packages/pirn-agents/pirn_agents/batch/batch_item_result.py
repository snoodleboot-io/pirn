"""``BatchItemResult`` — the isolated outcome of one item in a batch run."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

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
    exception:
        The captured :class:`ExceptionRecord` when ``status`` is
        ``ERROR``/``TIMEOUT``; otherwise ``None``. A fleet failure therefore
        carries the same fidelity — type, message, and detached traceback — as a
        per-knot failure, instead of a lossy one-line string.
    attempts:
        How many times the item was attempted (1 = succeeded first try).
    latency:
        Wall-clock seconds spent on the item (queue wait excluded).
    """

    #: :attr:`~pirn.managers.exception_record.ExceptionRecord.exc_type` values
    #: :meth:`from_result` treats as a timeout rather than a plain error.
    #: ``Result`` has no dedicated timeout variant (only ``Ok``/``Err``/
    #: ``Skipped``), so the distinction ``BatchItemStatus.TIMEOUT`` makes has
    #: to be recovered from the exception's recorded type name — a heuristic,
    #: not a structural guarantee. A caller that already knows which one
    #: applies should construct :class:`BatchItemResult` directly instead of
    #: routing through this bridge.
    _timeout_exc_types: ClassVar[frozenset[str]] = frozenset({"ToolTimeoutError", "TimeoutError"})

    index: int
    key: str
    status: BatchItemStatus
    output: Any = None
    exception: ExceptionRecord | None = None
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
        if self.exception is not None and not isinstance(self.exception, ExceptionRecord):
            raise TypeError(
                f"BatchItemResult: exception must be an ExceptionRecord, "
                f"got {type(self.exception).__name__}"
            )

    @property
    def succeeded(self) -> bool:
        """Whether the item completed successfully."""
        return self.status is BatchItemStatus.OK

    @property
    def error(self) -> str | None:
        """Human-readable failure detail, derived from :attr:`exception`.

        Read-only: the record is the single source of truth for a failure, and
        this is the one line of it a progress report or log line wants.
        """
        return None if self.exception is None else self.exception.message

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this result.

        ``output`` is stringified when it is not already a JSON primitive so the
        record stays serialisable for a durable sink without constraining what
        the agent may return. ``error`` is emitted alongside the full
        ``exception`` mapping so a reader written against the pre-record payload
        shape keeps working.
        """
        return {
            "index": self.index,
            "key": self.key,
            "status": self.status.value,
            "output": self._json_safe(self.output),
            "error": self.error,
            "exception": None if self.exception is None else self.exception.model_dump(mode="json"),
            "attempts": self.attempts,
            "latency": self.latency,
        }

    def to_result(self) -> Result[Any]:
        """Return this item's outcome as a core ``Result`` (``Ok | Err | Skipped``).

        ADR agents-speaks-core WS2 bridge, kept alongside :attr:`status` /
        :class:`BatchItemStatus` for one deprecation cycle rather than
        replacing them outright — ``MapAgent``'s scheduling (WS4b) still
        produces and consumes :class:`BatchItemResult` directly. ``TIMEOUT``
        has no dedicated ``Result`` variant; it becomes an ``Err`` exactly
        like ``ERROR``, distinguishable only via ``record.exc_type`` (see
        :meth:`from_result` for the reverse mapping).

        Returns:
            ``Ok(value=output)`` for ``OK``, ``Skipped`` for ``SKIPPED``, or
            ``Err(record=exception)`` for ``ERROR``/``TIMEOUT``.

        Raises:
            ValueError: If ``status`` is ``ERROR``/``TIMEOUT`` and
                :attr:`exception` is ``None`` — an ``Err`` cannot be built
                from a failure with no captured record.
        """
        if self.status is BatchItemStatus.OK:
            return Ok(value=self.output)
        if self.status is BatchItemStatus.SKIPPED:
            return Skipped(reason="resumed", detail={"index": self.index, "key": self.key})
        if self.exception is None:
            raise ValueError(
                f"BatchItemResult.to_result: status is {self.status.value!r} but "
                f"exception is None; cannot build an Err with no record"
            )
        return Err(record=self.exception)

    @classmethod
    def from_result(
        cls,
        *,
        index: int,
        key: str,
        result: Result[Any],
        attempts: int = 1,
        latency: float = 0.0,
    ) -> BatchItemResult:
        """Build a :class:`BatchItemResult` from a core ``Result``.

        The reverse of :meth:`to_result`. An ``Err`` maps to ``TIMEOUT`` when
        its record's ``exc_type`` is in :attr:`_timeout_exc_types`, else
        ``ERROR`` — see that attribute's docstring for why this is a
        heuristic rather than a structural mapping.

        Args:
            index: Position of the item in the input stream.
            key: Stable identity of the item.
            result: The core outcome to translate.
            attempts: How many times the item was attempted.
            latency: Wall-clock seconds spent on the item.
        """
        if isinstance(result, Ok):
            return cls(
                index=index,
                key=key,
                status=BatchItemStatus.OK,
                output=result.value,
                attempts=attempts,
                latency=latency,
            )
        if isinstance(result, Skipped):
            return cls(
                index=index,
                key=key,
                status=BatchItemStatus.SKIPPED,
                attempts=attempts,
                latency=latency,
            )
        status = (
            BatchItemStatus.TIMEOUT
            if result.record.exc_type in cls._timeout_exc_types
            else BatchItemStatus.ERROR
        )
        return cls(
            index=index,
            key=key,
            status=status,
            exception=result.record,
            attempts=attempts,
            latency=latency,
        )

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

        Accepts both the current shape and the pre-record shape, in which a
        failure carried only a bare ``error`` string — a checkpoint written by an
        older run must stay resumable.

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
            exception=cls._exception_from_payload(payload),
            attempts=int(payload.get("attempts", 1)),
            latency=float(payload.get("latency", 0.0)),
        )

    @staticmethod
    def _exception_from_payload(payload: Mapping[Any, Any]) -> ExceptionRecord | None:
        """Recover the failure record, lifting a legacy bare ``error`` string.

        A pre-record checkpoint has no traceback and no exception type to
        recover, so those are filled with the ``<unknown>`` sentinel rather than
        guessed at; the message the old run wrote is preserved verbatim.
        """
        raw = payload.get("exception")
        if raw is not None:
            return ExceptionRecord.model_validate(raw)
        error = payload.get("error")
        if error is None:
            return None
        return ExceptionRecord(
            run_id="<unbound>",
            knot_id=str(payload["key"]),
            exc_type="<unknown>",
            message=str(error),
            traceback_text="",
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
