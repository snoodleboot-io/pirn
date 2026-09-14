"""``ToolResult`` — the model-facing rendering of a tool call's ``Result``.

Since the ADR "agents speaks core" (WS1) a tool call is a knot, and its outcome
is the engine's ``Ok | Err | Skipped`` plus the ``KnotLineage`` row the run
records under the call's id — that is the source of truth every executor
reads. ``ToolResult`` carries that ``Result`` as its :attr:`outcome` and adds
only what a model (or a caller rendering for one) needs besides it: the call id,
latency and token annotations, and the derived model-facing text.
:class:`~pirn_agents.tools.tool_call_codec.ToolCallCodec` renders it for the
model, and every executor builds it through :meth:`from_result`.

There is no parallel outcome enum (PIR-872 deleted ``ToolStatus``): the
model-facing :attr:`status` is a string derived from the ``Result`` variant and
the error type — ``"ok"``, ``"error"``, ``"timeout"`` (an ``Err`` whose error
type is a timeout), or ``"skipped"``. A ``Skipped`` outcome renders as
``"skipped"``, not ``"error"`` (PIR-865): the call deliberately did not run —
most commonly a denied approval, whose ``Skipped`` carries core's propagated
``"approval_denied"`` reason (:mod:`pirn_agents.agent.tool_approval_check`,
PIR-872) — and the model is told exactly
that rather than that the tool failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.knot_lineage import KnotLineage
from pirn.core.ok import Ok
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord


@dataclass(frozen=True)
class ToolResult(PirnOpaqueValue):
    """The model-facing view of one tool call's ``Result`` (build it with :meth:`from_result`).

    Attributes
    ----------
    call_id:
        Identifier matching the originating :class:`ToolCall`.
    outcome:
        The call's core ``Ok | Err | Skipped``.
    latency:
        Wall-clock duration of the invocation in seconds, or ``None`` when
        not measured (a view built from a bare ``Result`` has no row to read
        it from).
    tokens:
        Token count attributable to the invocation, or ``None`` when not
        measured.
    """

    #: ``ExceptionRecord.exc_type`` values :attr:`status` renders as ``"timeout"``.
    _timeout_exc_types: ClassVar[frozenset[str]] = frozenset({"KnotTimeoutError", "TimeoutError"})

    call_id: str
    outcome: Result[Any]
    latency: float | None = None
    tokens: int | None = None

    def __post_init__(self) -> None:
        """Refuse an outcome that is not a core ``Result``.

        Raises:
            TypeError: If ``outcome`` is not an ``Ok``, ``Err``, or ``Skipped``.
        """
        if not isinstance(self.outcome, (Ok, Err, Skipped)):
            raise TypeError(
                f"ToolResult: outcome must be Ok, Err, or Skipped, "
                f"got {type(self.outcome).__name__}"
            )

    @property
    def succeeded(self) -> bool:
        """Whether the call's outcome is ``Ok``."""
        return isinstance(self.outcome, Ok)

    @property
    def result(self) -> Any:
        """The value the tool produced for an ``Ok`` outcome; otherwise ``None``."""
        return self.outcome.value if isinstance(self.outcome, Ok) else None

    @property
    def exception(self) -> ExceptionRecord | None:
        """The captured failure record for an ``Err`` outcome; otherwise ``None``."""
        return self.outcome.record if isinstance(self.outcome, Err) else None

    @property
    def error(self) -> str | None:
        """The model-facing failure text, or ``None`` for an ``Ok`` outcome.

        ``"<type>: <message>"`` for an ``Err`` — the shape every executor
        reported before the view existed — and ``"call skipped: <reason>"``
        for a ``Skipped``, the reason's underscores read as spaces (a denied
        approval's ``"approval_denied"`` reads ``"call skipped: approval
        denied"``).
        """
        if isinstance(self.outcome, Err):
            return f"{self.outcome.record.exc_type}: {self.outcome.record.message}"
        if isinstance(self.outcome, Skipped):
            return f"call skipped: {self.outcome.reason.replace('_', ' ')}"
        return None

    @property
    def status(self) -> str:
        """The model-facing status token derived from the outcome's variant and error type."""
        if isinstance(self.outcome, Ok):
            return "ok"
        if isinstance(self.outcome, Skipped):
            return "skipped"
        if (
            isinstance(self.outcome, Err)
            and self.outcome.record.exc_type in self._timeout_exc_types
        ):
            return "timeout"
        return "error"

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "result": repr(self.result),
            "error": self.error,
            "exception": (
                None if self.exception is None else self.exception.model_dump(mode="json")
            ),
            "status": self.status,
            "latency": self.latency,
            "tokens": self.tokens,
        }

    def with_latency(self, latency: float | None) -> ToolResult:
        """Return this view with ``latency`` attached (the outcome is unchanged)."""
        return ToolResult(
            call_id=self.call_id, outcome=self.outcome, latency=latency, tokens=self.tokens
        )

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
    ) -> ToolResult:
        """Build the view of one call's core ``Result`` — the one builder every path uses.

        Args:
            call_id: The originating :class:`~pirn_agents.tools.tool_call.ToolCall`'s
                identifier (a core ``Result`` carries no call id of its own).
            result: The call knot's ``Ok | Err | Skipped``.
            lineage: The call knot's lineage row, when the caller has it;
                supplies ``latency``.
            tokens: Token usage attributable to the call, when known.

        Returns:
            ``result.value`` unchanged when it is already a :class:`ToolResult`;
            otherwise a view carrying ``result``.

        Raises:
            TypeError: If ``result`` is not an ``Ok``, ``Err``, or ``Skipped``.
        """
        if isinstance(result, Ok) and isinstance(result.value, ToolResult):
            return result.value
        if not isinstance(result, (Ok, Err, Skipped)):
            raise TypeError(
                f"ToolResult.from_result: result must be Ok, Err, or Skipped, "
                f"got {type(result).__name__}"
            )
        return cls(call_id=call_id, outcome=result, latency=cls.latency_of(lineage), tokens=tokens)
