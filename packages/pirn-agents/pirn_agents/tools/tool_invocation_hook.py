"""``ToolInvocationHook`` — deprecated (one cycle) observability seam around tool calls.

Since the ADR "agents speaks core" (WS1) a tool call is a knot: its start,
end, outcome and latency are the ``KnotLineage`` row the engine records and
the status events the run's emitters already receive — there is no second
place to observe it from.  The hook stays importable for the cycle;
:class:`~pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor` still
fires it (``on_start`` before the graph runs, ``on_finish`` from the combine,
with a ``0.0`` latency) so an existing subscriber keeps its events, and the
base class warns when subclassed.

Contract for subclasses (unchanged for the cycle)
-------------------------------------------------
* ``on_start`` fires exactly once per call, before the batch runs.
* ``on_finish`` fires exactly once per call, for **every** terminal outcome
  (ok, error, timeout, tool-not-found), after the view is built.
* Implementations must be side-effect-free on the result path: the executor
  swallows any exception a hook raises.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn_agents.tools.tool_status import ToolStatus


class ToolInvocationHook:
    """Deprecated no-op observability hook fired around each tool call.

    Override :meth:`on_start` and :meth:`on_finish` to emit spans or metrics.
    The base methods do nothing by design.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        warnings.warn(
            f"{cls.__qualname__} subclasses ToolInvocationHook, which is deprecated (ADR "
            "agents-speaks-core WS1): observe tool calls through the run's lineage rows and "
            "emitters",
            DeprecationWarning,
            stacklevel=2,
        )

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
