"""``AgentAsToolMixin`` — adds ``.as_tool()`` to a ``SubTapestry`` agent.

Subclass this alongside your agent's pipeline base to expose the ergonomic
``agent.as_tool(...)`` API. The method simply delegates to the
:meth:`~pirn_agents.tools.as_tool.AsTool.wrap` free function, so the class adds no
state and leaves the agent's construction unchanged.

The ``SubTapestry`` requirement is expressed by *inheritance* rather than by an
assertion. Because :class:`AgentAsToolMixin` derives from
:class:`~pirn.nodes.sub_tapestry.SubTapestry`, ``self`` structurally is the
agent type :meth:`~pirn_agents.tools.as_tool.AsTool.wrap` accepts, so no ``typing.cast`` is needed to satisfy
the type checker and no mixer can opt out of the contract. It declares no
``__init__`` and no ``process``, so it contributes nothing to construction: a
mixer's ``super().__init__`` chain still reaches ``SubTapestry.__init__`` exactly
once, and ``process`` still resolves to the concrete agent's override.

The ``Mixin`` name says how it is used: combined with a pipeline base rather
than on its own.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.tools.as_tool import AsTool
from pirn_agents.tools.tool_declaration import ToolDeclaration

if TYPE_CHECKING:
    from pirn_agents.tools.agent_tool import AgentTool


class AgentAsToolMixin(SubTapestry):
    """A ``SubTapestry`` that can expose itself as an :class:`AgentTool`.

    Mix into a concrete agent — typically alongside
    :class:`~pirn_agents.specializations.base.agent_pipeline.AgentPipeline`, which
    is itself a ``SubTapestry`` — to gain :meth:`as_tool`. The shared
    ``SubTapestry`` base is inherited once through C3 linearization, so combining
    the two bases changes neither the MRO's construction path nor behaviour.
    """

    def declaration(self) -> ToolDeclaration:
        """The provider-neutral declaration of this agent as a tool (ADR agents-speaks-core, WS1).

        A ``SubTapestry`` is a ``Knot``, so nothing is needed to *run* it as a
        tool; the declaration — name, description, and the caller-facing
        subset of its ``process`` inputs — is what the model sees.
        """
        return AsTool.wrap(self).declaration()

    def as_tool(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        input_schema: Mapping[str, Any] | None = None,
        provider: LLMProvider | None = None,
        budget: RunBudget | None = None,
        max_depth: int = 8,
    ) -> AgentTool:
        """Return an :class:`AgentTool` wrapping this agent.

        See :meth:`~pirn_agents.tools.as_tool.AsTool.wrap` for the argument semantics.
        """
        return AsTool.wrap(
            self,
            name=name,
            description=description,
            input_schema=input_schema,
            provider=provider,
            budget=budget,
            max_depth=max_depth,
        )
