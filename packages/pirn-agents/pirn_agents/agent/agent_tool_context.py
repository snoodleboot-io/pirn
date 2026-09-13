"""``AgentToolContext`` — what an agent-as-tool call carries that core's nesting frame does not.

Core's :class:`~pirn.core.run_nesting.RunNesting` frame already travels with
every nested run: depth, the enclosing run ids, the container-class path, and
the tightest depth cap — and it is core that refuses an over-deep run or a
container re-entering itself (ADR agents-speaks-core, WS0/WS1).  Two things
are agents-only policy and still need to reach a nested agent through code
paths that forward no explicit state: the shared
:class:`~pirn_agents.performance.run_budget_meter.RunBudgetMeter` a whole
tree of agent-as-tool calls spends from, and the pooled
:class:`~pirn_agents.llm.llm_provider.LLMProvider` nested agents reuse by
identity.  ``AgentToolContext`` is a ``RunNesting`` frame extended with those
two, bound on a context variable around each agent-as-tool call.

The value is immutable: entering a nested agent produces a *new* child context
via :meth:`child`, so state never leaks across unrelated calls.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from pirn.core.run_nesting import RunNesting

from pirn_agents.agent.agent_nesting_config import AgentNestingConfig
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.run_budget_meter import RunBudgetMeter


@dataclass(frozen=True, slots=True)
class AgentToolContext(RunNesting):
    """Immutable snapshot of the active agent-as-tool state: a nesting frame plus policy.

    Attributes
    ----------
    depth, run_ids, path, max_depth:
        The core nesting frame this context was bound under (see
        :class:`RunNesting`); ``depth`` is ``0`` at the root.
    meter:
        Shared budget accountant threaded through every nested call, or ``None``
        when the caller configured no budget.
    provider:
        Shared pooled LLM provider reused by nested agents, or ``None`` when no
        provider is being propagated.
    """

    max_depth: int | None = AgentNestingConfig.max_depth
    meter: RunBudgetMeter | None = None
    provider: LLMProvider | None = None

    @property
    def stack(self) -> tuple[str, ...]:
        """The nesting keys on the path (the pre-ADR name for :attr:`path`)."""
        return self.path

    def child(
        self,
        key: str | None = None,
        parent_run_id: str | None = None,
        *,
        max_depth: int | None = None,
        meter: RunBudgetMeter | None = None,
        provider: LLMProvider | None = None,
    ) -> AgentToolContext:
        """Return the context for entering one more agent-as-tool call.

        The frame half follows :meth:`RunNesting.child` — one level deeper,
        *key* on the path — and so raises core's ``NestedRunCycleError`` /
        ``NestingDepthExceededError`` when a cap is active.  ``meter`` and
        ``provider`` default to the inherited values so a shared budget and
        pooled provider flow downward unchanged unless a nested tool
        explicitly overrides them.

        Args:
            key: Nesting key of the call being entered, or ``None`` for one
                that should not count toward cycle detection.
            parent_run_id: The enclosing run's id, when known.
            max_depth: A tighter cap to apply from here down.
            meter: Override budget meter; inherits :attr:`meter` when ``None``.
            provider: Override pooled provider; inherits :attr:`provider` when
                ``None``.
        """
        frame = RunNesting.child(self, key, parent_run_id or "", max_depth=max_depth)
        return AgentToolContext(
            depth=frame.depth,
            run_ids=frame.run_ids,
            path=frame.path,
            max_depth=frame.max_depth,
            meter=self.meter if meter is None else meter,
            provider=self.provider if provider is None else provider,
        )

    @staticmethod
    def from_current_frame(
        *, meter: RunBudgetMeter | None = None, provider: LLMProvider | None = None
    ) -> AgentToolContext:
        """A context over the nesting frame of the run executing right now."""
        frame = RunNesting.current()
        return AgentToolContext(
            depth=frame.depth,
            run_ids=frame.run_ids,
            path=frame.path,
            max_depth=frame.max_depth,
            meter=meter,
            provider=provider,
        )

    @staticmethod
    def bound() -> AgentToolContext | None:
        """Return the bound :class:`AgentToolContext`, or ``None`` when none is bound."""
        return _current_agent_tool_context.get()

    @staticmethod
    def current() -> AgentToolContext:
        """The active context: the bound one, else a policy-free view of the running frame."""
        bound = _current_agent_tool_context.get()
        return bound if bound is not None else AgentToolContext.from_current_frame()

    @staticmethod
    @contextmanager
    def bind(context: AgentToolContext) -> Iterator[None]:
        """Bind ``context`` as the active context for the duration of the block.

        Restores the prior context on exit so nesting state never leaks past
        the invocation that established it, even when an exception unwinds
        the stack.
        """
        token = _current_agent_tool_context.set(context)
        try:
            yield
        finally:
            _current_agent_tool_context.reset(token)


_current_agent_tool_context: ContextVar[AgentToolContext | None] = ContextVar(
    "_current_agent_tool_context", default=None
)


def current_agent_tool_context() -> AgentToolContext | None:
    """Return the active :class:`AgentToolContext`, or ``None`` at the root.

    Thin wrapper kept for the documented public import path (see
    ``tests/test_ws5_s1_import_surface.py``); see :meth:`AgentToolContext.bound`.
    """
    return AgentToolContext.bound()


def bind_agent_tool_context(context: AgentToolContext) -> AbstractContextManager[None]:
    """Bind ``context`` as the active context for the duration of the block.

    Thin wrapper kept for the documented public import path (see
    ``tests/test_ws5_s1_import_surface.py``); see :meth:`AgentToolContext.bind`.
    """
    return AgentToolContext.bind(context)
