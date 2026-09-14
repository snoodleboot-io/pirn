"""``WorkerInvocation`` — invoke one worker for one task, admission-bounded."""

from __future__ import annotations

from typing import Any

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult


class WorkerInvocation(Knot):
    """Invoke one worker for one task.

    Never raises: a failed call becomes a :class:`ToolResult` whose outcome is ``Err``. An F7
    :class:`~pirn_agents.tools.agent_tool.AgentTool`'s own ``ToolResult`` is
    passed through unchanged rather than double-wrapped, matching
    ``AgentTool.invoke()``'s documented contract of never raising itself.

    How many of these run at once is bounded by the engine's own admission
    gate — :class:`~pirn_agents.specializations.multi_agent.orchestrator_workers.OrchestratorWorkers`
    puts every instance in the same ``KnotConfig.concurrency_group`` and
    sets a matching ``ConcurrencyLimits`` group cap on the inner run (PIR-867;
    the same lever :class:`~pirn_agents.batch.map_agent.MapAgent` uses) —
    rather than by a shared ``asyncio.Semaphore`` held across the call.
    """

    def __init__(
        self,
        *,
        task: Knot | str,
        worker: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, worker=worker, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        worker: ToolFactory,
        **_: Any,
    ) -> ToolResult:
        """Invoke ``worker`` for ``task``, never raising.

        Args:
            task: The task string handed to the worker.
            worker: The tool (in practice an F7 agent-as-tool) to invoke.

        Returns:
            The worker's own :class:`ToolResult` when it returns one already
            (an F7 :class:`~pirn_agents.tools.agent_tool.AgentTool`), or a
            :class:`ToolResult` wrapping its plain return value, or a
            :class:`ToolResult` whose outcome is ``Err`` when the call raised.
        """
        factory = ToolFactory.of(worker)
        call = ToolCall(tool_name=factory.name, arguments={"task": task}, call_id=task)
        try:
            outcome = await factory.run_call(call)
        except ToolArgumentValidationError as exc:
            return ToolResult(call_id=task, outcome=Err(record=ExceptionRecord.for_knot(task, exc)))
        return ToolResult.from_result(task, outcome)
