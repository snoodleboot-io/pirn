"""The outcome of a single :class:`ToolCall`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.tools.tool_status import ToolStatus


@dataclass(frozen=True)
class ToolResult(PirnOpaqueValue):
    """Result returned by invoking a tool.

    Attributes
    ----------
    call_id:
        Identifier matching the originating :class:`ToolCall`.
    result:
        Raw value the tool produced. May be any python object.
    error:
        Human-readable failure detail, or ``None`` when the invocation
        succeeded. Derived from ``exception`` when one is supplied and this is
        left unset, so the two never disagree.
    exception:
        The captured :class:`ExceptionRecord` when the failure came from a
        python exception; ``None`` otherwise. The tool path used to keep only
        the stringified message, so a caller could see *that* a tool failed but
        not the type or the traceback — the low-fidelity reporting the batch
        path shed in PIR-724 (PIR-794).

        It stays optional because not every failure has an exception behind it:
        an MCP tool reporting a protocol-level error, for instance, has a
        message and nothing to capture. Such a caller passes ``error`` alone
        rather than fabricating a record.
    status:
        Terminal disposition of the invocation. Defaults to
        :attr:`ToolStatus.OK`; when left at the default and ``error`` is
        set, it is promoted to :attr:`ToolStatus.ERROR` in
        ``__post_init__``. An explicit non-OK status (``TIMEOUT``) is
        always preserved.
    latency:
        Wall-clock duration of the invocation in seconds, or ``None`` when
        not measured.
    tokens:
        Token count attributable to the invocation, or ``None`` when not
        measured.
    """

    call_id: str
    result: Any
    error: str | None = None
    status: ToolStatus = ToolStatus.OK
    latency: float | None = None
    tokens: int | None = None
    exception: ExceptionRecord | None = None

    def __post_init__(self) -> None:
        """Fill ``error`` from ``exception``, then derive ``status``.

        Frozen-safe: uses ``object.__setattr__`` to mutate the fields.

        ``error`` is filled from the record rather than being a read-only
        property, unlike
        :attr:`~pirn_agents.batch.batch_item_result.BatchItemResult.error`.
        That type could make it derived because it was built that way from the
        start; here ``error`` is long-standing public API set directly by many
        call sites, some of which have no exception object to offer. Deriving it
        only when it was not supplied keeps both kinds of caller working and
        still leaves one message when a record IS given.

        ``status`` is only ever promoted from the default ``OK`` to ``ERROR``,
        so an explicitly supplied ``TIMEOUT`` is never overwritten.

        Raises:
            TypeError: If ``exception`` is neither ``None`` nor an
                :class:`ExceptionRecord`.
        """
        if self.exception is not None and not isinstance(self.exception, ExceptionRecord):
            raise TypeError(
                f"ToolResult: exception must be an ExceptionRecord, "
                f"got {type(self.exception).__name__}"
            )
        if self.error is None and self.exception is not None:
            object.__setattr__(self, "error", self.exception.message)
        if self.error is not None and self.status == ToolStatus.OK:
            object.__setattr__(self, "status", ToolStatus.ERROR)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "result": repr(self.result),
            "error": self.error,
            "exception": (
                None if self.exception is None else self.exception.model_dump(mode="json")
            ),
            "status": self.status.value,
            "latency": self.latency,
            "tokens": self.tokens,
        }

    def to_result(self) -> Result[ToolResult]:
        """Return the core ``Ok | Err | Skipped`` view of this outcome.

        This is a bridging step (WS3·S1 is deferred — see the note at
        :meth:`pirn_agents.tools.tool_invocation.ToolInvocation.process`), not
        a migration: :class:`ToolResult` remains the value every existing
        caller sees. Nothing here loses information — an :attr:`ToolStatus.OK`
        or :attr:`ToolStatus.ERROR` result maps one-to-one onto ``Ok``/``Err``.

        Returns:
            ``Ok(value=self)`` for :attr:`ToolStatus.OK`; otherwise
            ``Err(record=...)``, using :attr:`exception` when the failure came
            from a captured python exception, or a synthetic
            :class:`~pirn.managers.exception_record.ExceptionRecord` built from
            :attr:`error` (or the status name, if ``error`` is unset — a bare
            :attr:`ToolStatus.TIMEOUT` from a caller that never populated it)
            otherwise. ``Skipped`` is never produced: :class:`ToolStatus` has
            no "not run" member, so there is nothing in ``self`` that would map
            to it.
        """
        if self.status is ToolStatus.OK:
            return Ok(value=self)
        if self.exception is not None:
            return Err(record=self.exception)
        message = self.error if self.error is not None else f"tool status {self.status.value}"
        return Err(record=ExceptionRecord.for_knot(self.call_id, RuntimeError(message)))

    @classmethod
    def from_result(cls, call_id: str, result: Result[Any]) -> ToolResult:
        """Build a :class:`ToolResult` from a core ``Ok | Err | Skipped``.

        The inverse of :meth:`to_result`, for callers that hold a core
        ``Result`` (e.g. a :class:`~pirn.core.knot.Knot` output) and need the
        :class:`ToolResult` shape the rest of this package expects.

        Args:
            call_id: The originating :class:`~pirn_agents.tools.tool_call.ToolCall`'s
                identifier, echoed onto the returned :class:`ToolResult` (a
                core ``Result`` carries no call id of its own).
            result: The core result to convert.

        Returns:
            ``result.value`` unchanged when it is already a :class:`ToolResult`
            (round-tripping :meth:`to_result`'s ``Ok`` case exactly); otherwise
            a fresh :attr:`ToolStatus.OK` result wrapping a non-``ToolResult``
            ``Ok`` value, an :attr:`ToolStatus.ERROR` result carrying ``Err``'s
            record, or an :attr:`ToolStatus.ERROR` result describing the skip
            when given a ``Skipped`` — :class:`ToolStatus` has no "not run"
            member, so a skip is reported as its own kind of error rather than
            silently reclassified as one the caller did not make.

        Raises:
            TypeError: If ``result`` is not an ``Ok``, ``Err``, or ``Skipped``.
        """
        if isinstance(result, Ok):
            if isinstance(result.value, ToolResult):
                return result.value
            return cls(call_id=call_id, result=result.value, status=ToolStatus.OK)
        if isinstance(result, Err):
            return cls(
                call_id=call_id, result=None, status=ToolStatus.ERROR, exception=result.record
            )
        if isinstance(result, Skipped):
            return cls(
                call_id=call_id,
                result=None,
                status=ToolStatus.ERROR,
                error=f"skipped: {result.reason}",
            )
        raise TypeError(
            f"ToolResult.from_result: result must be Ok, Err, or Skipped, got {type(result).__name__}"
        )
