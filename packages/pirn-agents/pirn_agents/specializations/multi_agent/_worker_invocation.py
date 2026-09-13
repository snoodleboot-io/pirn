"""``_WorkerInvocation`` — invoke one worker for one task, semaphore-bounded."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult


class _WorkerInvocation(Knot):
    """Invoke one worker for one task, bounded by a shared semaphore.

    Never raises: a failed call becomes a ``ToolStatus.ERROR`` result. An F7
    :class:`~pirn_agents.tools.agent_tool.AgentTool`'s own ``ToolResult`` is
    passed through unchanged rather than double-wrapped, matching
    ``AgentTool.invoke()``'s documented contract of never raising itself.

    ``semaphore`` is typed ``Any``, justified: it is a coordination primitive
    rather than a domain value, and pydantic has no schema for
    ``asyncio.Semaphore`` — ``Knot.__init__`` builds a ``TypeAdapter`` for
    every declared input eagerly, so a concrete ``asyncio.Semaphore``
    annotation raises ``PydanticSchemaGenerationError`` at construction time
    regardless of ``_config.validate_io``.
    """

    def __init__(
        self,
        *,
        task: Knot | str,
        worker: Knot | Any,
        semaphore: Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, worker=worker, semaphore=semaphore, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        worker: ToolFactory,
        semaphore: Any,
        **_: Any,
    ) -> ToolResult:
        """Invoke ``worker`` for ``task`` under ``semaphore``, never raising.

        Args:
            task: The task string handed to the worker.
            worker: The tool (in practice an F7 agent-as-tool) to invoke.
            semaphore: Shared budget bounding simultaneously in-flight calls.

        Returns:
            The worker's own :class:`ToolResult` when it returns one already
            (an F7 :class:`~pirn_agents.tools.agent_tool.AgentTool`), or a
            :class:`ToolResult` wrapping its plain return value, or a
            :class:`ToolResult` with :attr:`ToolStatus.ERROR` when the call
            raised.
        """
        factory = ToolFactory.of(worker)
        call = ToolCall(tool_name=factory.name, arguments={"task": task}, call_id=task)
        async with semaphore:
            try:
                outcome = await factory.run_call(call)
            except ToolArgumentValidationError as exc:
                return ToolResult(call_id=task, result=None, error=str(exc))
        return ToolResult.from_result(task, outcome)
