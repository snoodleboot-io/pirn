"""``AgentToolPolicy`` — the budget and provider an agent-as-tool tree shares.

Where a nested agent-as-tool call sits in the run tree, how deep it may go and
whether it re-enters itself are core's business: every nested run carries a
:class:`~pirn.core.run_nesting.RunNesting` frame (``RunNesting.current()``),
and ``Tapestry(max_nesting_depth=)`` refuses an over-deep run
(``NestingDepthExceededError``) or a container re-entering itself
(``NestedRunCycleError``).  This class carries none of that.

What core has no name for is agents-only policy that must reach a nested agent
through code paths that forward no explicit state: the shared
:class:`~pirn_agents.performance.run_budget_meter.RunBudgetMeter` a whole tree
of agent-as-tool calls spends from, and the pooled
:class:`~pirn_agents.llm.llm_provider.LLMProvider` nested agents reuse by
identity.  ``AgentToolPolicy`` is exactly that pair, bound on a context
variable around each agent-as-tool call by
:class:`~pirn_agents.tools.agent_tool_call.AgentToolCall`.

The value is immutable; binding restores the prior policy on exit, so state
never leaks across unrelated calls.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import ClassVar

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.run_budget_meter import RunBudgetMeter


@dataclass(frozen=True, slots=True)
class AgentToolPolicy:
    """Immutable budget/provider policy for the active agent-as-tool call.

    Attributes
    ----------
    meter:
        Shared budget accountant threaded through every nested call, or ``None``
        when the caller configured no budget.
    provider:
        Shared pooled LLM provider reused by nested agents, or ``None`` when no
        provider is being propagated.
    """

    #: The active policy for this context (``None`` outside any agent-as-tool call).
    _current: ClassVar[ContextVar[AgentToolPolicy | None]] = ContextVar(
        "_current_agent_tool_policy", default=None
    )

    meter: RunBudgetMeter | None = None
    provider: LLMProvider | None = None

    @staticmethod
    def bound() -> AgentToolPolicy | None:
        """Return the bound :class:`AgentToolPolicy`, or ``None`` when none is bound."""
        return AgentToolPolicy._current.get()

    @staticmethod
    def current() -> AgentToolPolicy:
        """The active policy: the bound one, else an empty policy."""
        bound = AgentToolPolicy._current.get()
        return bound if bound is not None else AgentToolPolicy()

    @staticmethod
    @contextmanager
    def bind(policy: AgentToolPolicy) -> Generator[None, None, None]:
        """Bind ``policy`` as the active policy for the duration of the block.

        Restores the prior policy on exit, even when an exception unwinds the
        stack.
        """
        token = AgentToolPolicy._current.set(policy)
        try:
            yield
        finally:
            AgentToolPolicy._current.reset(token)
