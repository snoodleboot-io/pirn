"""The outcome of a single :class:`ToolCall`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
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
