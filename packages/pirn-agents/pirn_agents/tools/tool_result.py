"""``ToolResult`` — the deprecated, one-cycle view of a tool call's ``Result``.

Since the ADR "agents speaks core" (WS1) a tool call is a knot, and its outcome
is the engine's ``Ok | Err | Skipped`` plus the ``KnotLineage`` row the run
records under the call's id — that is what a codec, a synthesiser or a
session reads now.  ``ToolResult`` remains for one deprecation cycle as a
*view* over that pair for callers that still expect the pre-ADR shape: every
executor builds it through the single :meth:`from_result`, and nothing else
constructs one.  ``latency`` is derived from the lineage row's timestamps
when a row is given and is ``None`` otherwise; ``tokens`` is a caller-supplied
annotation a bare ``Result`` never carries.

A ``Skipped`` outcome renders as :attr:`~pirn_agents.tools.tool_status.ToolStatus.SKIPPED`
(PIR-865), not ``ERROR``: the call deliberately did not run — most commonly a
denied approval, see :meth:`from_result`'s ``gated`` argument and
:mod:`pirn_agents.agent.tool_approval_check` — and a caller (or the model, via
:class:`~pirn_agents.tools.tool_call_codec.ToolCallCodec`) is told exactly
that rather than that the tool failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.err import Err
from pirn.core.knot_lineage import KnotLineage
from pirn.core.ok import Ok
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.tools.tool_status import ToolStatus


@dataclass(frozen=True)
class ToolResult(PirnOpaqueValue):
    """Deprecated view of one tool call's ``Result`` (build it with :meth:`from_result`).

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
        python exception; ``None`` otherwise — an MCP tool reporting a
        protocol-level error has a message and nothing to capture, and such a
        caller passes ``error`` alone rather than fabricating a record.
    status:
        Terminal disposition of the invocation. Defaults to
        :attr:`ToolStatus.OK`; when left at the default and ``error`` is
        set, it is promoted to :attr:`ToolStatus.ERROR` in
        ``__post_init__``. An explicit non-OK status (``TIMEOUT``,
        ``SKIPPED``) is always preserved.
    latency:
        Wall-clock duration of the invocation in seconds, or ``None`` when
        not measured (a view built from a bare ``Result`` has no row to read
        it from).
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

        ``error`` is filled from the record's ``"<type>: <message>"`` when it
        was not supplied — the shape every executor reported before the view
        existed — so the message and the record cannot drift apart.
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
            object.__setattr__(
                self, "error", f"{self.exception.exc_type}: {self.exception.message}"
            )
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

        Returns:
            ``Ok(value=self)`` for :attr:`ToolStatus.OK`; ``Skipped(reason=...)``
            for :attr:`ToolStatus.SKIPPED`, reading the reason back out of
            :attr:`error` (PIR-865: round-trips the skip a gated
            :meth:`from_result` recorded there); otherwise ``Err(record=...)``,
            using :attr:`exception` when the failure came from a captured
            python exception, or a synthetic
            :class:`~pirn.managers.exception_record.ExceptionRecord` built from
            :attr:`error` (or the status name, if ``error`` is unset)
            otherwise.
        """
        if self.status is ToolStatus.OK:
            return Ok(value=self)
        if self.status is ToolStatus.SKIPPED:
            return Skipped(reason=self.error if self.error is not None else "skipped")
        if self.exception is not None:
            return Err(record=self.exception)
        message = self.error if self.error is not None else f"tool status {self.status.value}"
        return Err(record=ExceptionRecord.for_knot(self.call_id, RuntimeError(message)))

    @staticmethod
    def latency_of(lineage: KnotLineage | None) -> float | None:
        """Seconds between a lineage row's ``started_at`` and ``finished_at``, or ``None``."""
        if lineage is None:
            return None
        return (lineage.finished_at - lineage.started_at).total_seconds()

    @classmethod
    def from_result(
        cls,
        call_id: str,
        result: Result[Any],
        lineage: KnotLineage | None = None,
        *,
        tokens: int | None = None,
        gated: bool = False,
    ) -> ToolResult:
        """Build the view of one call's core ``Result`` — the one builder every path uses.

        Args:
            call_id: The originating :class:`~pirn_agents.tools.tool_call.ToolCall`'s
                identifier (a core ``Result`` carries no call id of its own).
            result: The call knot's ``Ok | Err | Skipped``.
            lineage: The call knot's lineage row, when the caller has it;
                supplies ``latency``.
            tokens: Token usage attributable to the call, when known.
            gated: ``True`` when the caller wired an approval
                :class:`~pirn.nodes.gate.gate.Gate` in front of this call
                (:meth:`~pirn_agents.tools.tool_factory.ToolFactory.for_call`,
                PIR-865). A gated call's only possible parent besides its own
                (always-``Ok``) arguments is that gate, so a ``Skipped``
                result can only be the gate closing — the message names
                :attr:`~pirn_agents.agent.tool_approval_check.ToolApprovalCheck.skip_reason`
                ("approval denied") rather than the engine's generic
                propagation reason. Ignored for ``Ok``/``Err``.

        Returns:
            ``result.value`` unchanged when it is already a :class:`ToolResult`;
            otherwise an ``OK`` view of an ``Ok`` value, an ``ERROR`` view
            carrying ``Err``'s record — ``TIMEOUT`` when the record is core's
            ``KnotTimeoutError``, i.e. the call outlived ``KnotConfig.timeout``
            — or a ``SKIPPED`` view of a ``Skipped`` (PIR-865): the call
            deliberately did not run, and the model is told exactly that
            rather than that it failed.

        Raises:
            TypeError: If ``result`` is not an ``Ok``, ``Err``, or ``Skipped``.
        """
        latency = cls.latency_of(lineage)
        if isinstance(result, Ok):
            if isinstance(result.value, ToolResult):
                return result.value
            return cls(
                call_id=call_id,
                result=result.value,
                status=ToolStatus.OK,
                latency=latency,
                tokens=tokens,
            )
        if isinstance(result, Err):
            timed_out = result.record.exc_type == "KnotTimeoutError"
            return cls(
                call_id=call_id,
                result=None,
                status=ToolStatus.TIMEOUT if timed_out else ToolStatus.ERROR,
                exception=result.record,
                latency=latency,
            )
        if isinstance(result, Skipped):
            reason = "approval denied" if gated else result.reason
            return cls(
                call_id=call_id,
                result=None,
                status=ToolStatus.SKIPPED,
                error=f"call skipped: {reason}",
                latency=latency,
            )
        raise TypeError(
            f"ToolResult.from_result: result must be Ok, Err, or Skipped, got {type(result).__name__}"
        )
