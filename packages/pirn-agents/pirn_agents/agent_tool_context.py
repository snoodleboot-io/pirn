"""``AgentToolContext`` — ambient per-invocation state for agent-as-tool nesting.

One immutable context value is threaded through nested agent-as-tool calls via a
private :class:`contextvars.ContextVar` (mirroring the framework's own
``pirn.tapestry._current_tapestry`` pattern). Because a nested :class:`AgentTool`
is dispatched deep inside another agent's ReAct loop — through code paths that do
not forward any explicit state — a context var is the only way to propagate the
recursion depth, the active call stack (for cycle detection), the shared
:class:`~pirn_agents.performance.run_budget_meter.RunBudgetMeter`, and the shared
pooled :class:`~pirn.core.providers.llm_provider.LLMProvider` down the tree.

The value is immutable: entering a nested agent produces a *new* child context
via :meth:`AgentToolContext.child`, which enforces the depth cap and cycle
check before returning. State therefore never leaks across unrelated calls — a
sibling invocation reads the parent context, not a mutated one.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.exceptions.agent_cycle_error import AgentCycleError
from pirn_agents.exceptions.agent_depth_exceeded_error import (
    AgentDepthExceededError,
)
from pirn_agents.performance.run_budget_meter import RunBudgetMeter


@dataclass(frozen=True)
class AgentToolContext:
    """Immutable snapshot of the active agent-as-tool nesting state.

    Attributes
    ----------
    depth:
        Number of agent-as-tool frames currently active (``0`` at the root).
    stack:
        Agent identity keys active from outermost to innermost, used for cycle
        detection.
    max_depth:
        The maximum permitted nesting depth for this subtree.
    meter:
        Shared budget accountant threaded through every nested call, or ``None``
        when the caller configured no budget.
    provider:
        Shared pooled LLM provider reused by nested agents, or ``None`` when no
        provider is being propagated.
    """

    depth: int = 0
    stack: tuple[str, ...] = ()
    max_depth: int = 8
    meter: RunBudgetMeter | None = None
    provider: LLMProvider | None = field(default=None)

    def child(
        self,
        key: str,
        *,
        meter: RunBudgetMeter | None = None,
        provider: LLMProvider | None = None,
    ) -> AgentToolContext:
        """Return the child context for entering agent ``key``.

        Enforces the guards *before* returning, so an unsafe frame is never
        created: a ``key`` already on :attr:`stack` raises
        :class:`AgentCycleError`, and exceeding :attr:`max_depth` raises
        :class:`AgentDepthExceededError`. ``meter``/``provider`` default to the
        inherited values so a shared budget and pooled provider flow downward
        unchanged unless a nested tool explicitly overrides them.

        Args:
            key: Stable identity of the agent about to be entered.
            meter: Override budget meter; inherits :attr:`meter` when ``None``.
            provider: Override pooled provider; inherits :attr:`provider` when
                ``None``.

        Returns:
            A new :class:`AgentToolContext` one level deeper.

        Raises:
            AgentCycleError: If ``key`` is already active on the stack.
            AgentDepthExceededError: If the child depth exceeds ``max_depth``.
        """
        if key in self.stack:
            raise AgentCycleError(key, self.stack)
        next_depth = self.depth + 1
        if next_depth > self.max_depth:
            raise AgentDepthExceededError(next_depth, self.max_depth)
        return AgentToolContext(
            depth=next_depth,
            stack=(*self.stack, key),
            max_depth=self.max_depth,
            meter=self.meter if meter is None else meter,
            provider=self.provider if provider is None else provider,
        )


_current_agent_tool_context: ContextVar[AgentToolContext | None] = ContextVar(
    "_current_agent_tool_context", default=None
)


def current_agent_tool_context() -> AgentToolContext | None:
    """Return the active :class:`AgentToolContext`, or ``None`` at the root."""
    return _current_agent_tool_context.get()


@contextmanager
def bind_agent_tool_context(context: AgentToolContext) -> Iterator[None]:
    """Bind ``context`` as the active context for the duration of the block.

    Restores the prior context on exit so nesting state never leaks past the
    invocation that established it, even when an exception unwinds the stack.
    """
    token = _current_agent_tool_context.set(context)
    try:
        yield
    finally:
        _current_agent_tool_context.reset(token)
