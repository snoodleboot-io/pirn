"""Observability interface for individual tool invocations.

:class:`ToolInvocationHook` is the seam that lets an application observe every
tool call an executor runs — one ``on_start`` before the tool is invoked and
one ``on_finish`` after its :class:`~pirn_agents.types.tool_result.ToolResult`
is built — without the executor knowing anything about spans, metrics, or logs.

The base class is a genuine, intentional **no-op**: its methods return ``None``
and do nothing. That is the *default behaviour*, not a placeholder — an executor
handed no hook (or the base hook) does zero observability work, and passing the
base class is indistinguishable from passing nothing. Subclasses override the
two methods to emit tracing spans, counters, or histograms; those overrides are
what feed the metrics (F10) and tracing (F23) surfaces.

Contract for subclasses
-----------------------
* ``on_start`` fires exactly once per call, immediately before the tool runs.
* ``on_finish`` fires exactly once per call, for **every** terminal outcome
  (ok, error, timeout, tool-not-found), after the result is built.
* Implementations must be side-effect-free on the result path: an executor is
  free to swallow any exception a hook raises so observability can never abort
  or alter tool execution. Hooks should therefore avoid raising, but a raising
  hook must never be relied upon to change control flow.
"""

from __future__ import annotations

from pirn_agents.types.tool_status import ToolStatus


class ToolInvocationHook:
    """No-op observability hook fired around each tool invocation.

    Override :meth:`on_start` and :meth:`on_finish` to emit spans or metrics.
    The base methods do nothing by design; the unmodified class is the
    zero-cost default an executor uses when no observability is wired.
    """

    def on_start(self, *, tool_name: str, args_digest: str, call_id: str) -> None:
        """Signal that a tool is about to be invoked.

        Args:
            tool_name: Name of the tool being invoked.
            args_digest: Short, stable digest of the call's arguments, safe to
                record without exposing raw argument values.
            call_id: Identifier of the originating call, correlating this event
                with the matching :meth:`on_finish`.

        Returns:
            ``None``. The base implementation is a deliberate no-op.
        """
        return None

    def on_finish(
        self, *, tool_name: str, call_id: str, status: ToolStatus, latency: float
    ) -> None:
        """Signal that a tool invocation has reached a terminal outcome.

        Args:
            tool_name: Name of the tool that was invoked.
            call_id: Identifier of the originating call, matching the earlier
                :meth:`on_start` event.
            status: Terminal disposition of the invocation (ok, error, timeout).
            latency: Wall-clock duration of the invocation in seconds.

        Returns:
            ``None``. The base implementation is a deliberate no-op.
        """
        return None
