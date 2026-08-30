"""``ToolInvocation`` — one tool call as a graph node.

A tool call is a unit of work the framework already knows how to run, but until
now it ran outside the engine: ``Tool.invoke(arguments)`` was awaited directly
by :class:`~pirn_agents.planning.tool_executor.ToolExecutor` and
:class:`~pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor`, so a
tool call produced no ``Result``, no ``KnotLineage`` row, and nothing the
engine could schedule, cache or replay. ``Tool.invoke`` was in effect a second
execution primitive parallel to ``Knot.process`` (PIR-733).

This knot closes that gap by making the **call** the knot, not the tool. The
distinction matters:

* ``Tool`` stays a :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` — a
  capability the agent holds and may invoke many times, with identity-keyed
  serialisation so content-addressing stays stable. Turning ``Tool`` itself
  into a ``Knot`` would conflate the capability with a single use of it, and
  every tool would need a graph identity it has no use for.
* ``ToolInvocation`` is one use: it has a ``KnotConfig.id``, it appears in
  lineage, and N of them can be wired as parents of an
  :class:`~pirn.nodes.aggregator.Aggregator` so the *engine* schedules the
  wave — the same shape PIR-714 used for specialist fan-out.

The tool is passed to ``super().__init__`` rather than held on a ``_mutable_``
slot (which is what :class:`~pirn_agents.specializations.multi_agent.specialist_invocation.SpecialistInvocation`
must do). A ``Tool`` is not a ``Knot``, so core partitions it as a *config
value* rather than a parent, which is exactly right: it is data this knot
invokes, and as a config value it is covered by the lineage row's
``config_values_hash`` (PIR-836) so two invocations of *different* tools are
distinguishable in provenance.

One consequence of that, stated because it is a real limit rather than an
oversight: ``Tool`` is identity-keyed, so its content hash differs across
processes. A recorded run replayed in a new process will find the
``config_values_hash`` changed and refuse to serve the recorded output
(``ReplayMismatchError``), rather than silently substituting a value recorded
against a possibly-different tool. That is the safe direction of the trade —
see ``InvocationIdentity.is_comparable``.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus


class ToolInvocation(Knot):
    """Invoke one :class:`Tool` for one :class:`ToolCall`, inside the engine."""

    # A tool's exception message routinely carries whatever it was talking to,
    # including a DSN. ``ToolExecutor`` scrubbed it; ``ParallelToolExecutor`` did
    # not, because it captured the raw ``ExceptionRecord`` — so the *batch* path
    # wrote live credentials into ``ToolResult.error`` and into the lineage row's
    # exception record, which persists to history. Scrubbing here fixes both
    # paths at the boundary rather than leaving it to each caller to remember.
    _scrubber: ClassVar[DsnScrubber] = DsnScrubber()

    def __init__(
        self,
        *,
        tool: Tool,
        call: Knot | ToolCall,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Wire a single tool call as a graph node.

        Args:
            tool: The capability to invoke. Not a ``Knot``, so core partitions
                it as a config value rather than a parent.
            call: The :class:`ToolCall` to execute, either as a literal or as an
                upstream knot the engine resolves first.
            _config: Framework metadata; ``id`` is required as for any knot.

        Raises:
            TypeError: If ``tool`` is not a :class:`Tool`.
        """
        if not isinstance(tool, Tool):
            raise TypeError(f"ToolInvocation: tool must be a Tool, got {type(tool).__name__}")
        super().__init__(tool=tool, call=call, _config=_config, **kwargs)

    async def process(self, tool: Tool, call: ToolCall, **_: Any) -> ToolResult:
        """Invoke ``tool`` for ``call`` and return its terminal :class:`ToolResult`.

        A raised exception becomes a :attr:`ToolStatus.ERROR` result carrying an
        :class:`ExceptionRecord` rather than propagating. That is deliberate and
        differs from a plain knot, which would let the engine wrap the raise as
        ``Err``: the callers this replaces — both executors and
        :meth:`BaseTool.as_tool_result` — treat a failed call as a *value* to be
        reported per call, not as a failure of the surrounding batch, and a
        sibling call must not be skipped because this one raised.

        Migrating ``ToolResult`` onto core's ``Ok | Err | Skipped`` is WS3·S1 and
        deliberately not done here; when it lands, this method is the single
        place that changes.

        Args:
            tool: The resolved tool (a config value, not an upstream input).
            call: The resolved :class:`ToolCall`.

        Returns:
            A :class:`ToolResult` echoing ``call.call_id``, with measured
            ``latency`` and either the tool's value or the captured error.

        Raises:
            TypeError: If ``call`` is not a :class:`ToolCall`.
        """
        if not isinstance(call, ToolCall):
            raise TypeError(f"ToolInvocation: call must be a ToolCall, got {type(call).__name__}")
        start = time.perf_counter()
        try:
            value = await tool.invoke(call.arguments)
        except Exception as exc:
            scrubber = type(self)._scrubber
            raw = ExceptionRecord.for_knot(call.tool_name, exc)
            # Both fields carry the message, so scrubbing only ``message`` would
            # leave the credential in the traceback. The record is frozen, so
            # this is a copy rather than a mutation; the exception object itself
            # is never reconstructed, which would fail for any exception whose
            # constructor takes more than a message.
            record = raw.model_copy(
                update={
                    "message": scrubber.scrub(raw.message),
                    "traceback_text": scrubber.scrub(raw.traceback_text),
                }
            )
            return ToolResult(
                call_id=call.call_id,
                result=None,
                status=ToolStatus.ERROR,
                error=f"{type(exc).__name__}: {record.message}",
                exception=record,
                latency=time.perf_counter() - start,
            )
        return ToolResult(
            call_id=call.call_id,
            result=value,
            status=ToolStatus.OK,
            latency=time.perf_counter() - start,
        )
