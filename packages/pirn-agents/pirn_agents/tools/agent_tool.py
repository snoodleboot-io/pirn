"""``AgentTool`` — a ``SubTapestry`` agent as a tool capability.

A ``SubTapestry`` IS a ``Knot``, so an agent needs no adapter to be *executed*
as a tool (ADR agents-speaks-core, WS1).  What remains of the pre-ADR wrapper
is the declaration policy that is specific to agents — which of the agent's
inputs are caller-facing task inputs (versus injected collaborators such as
``llm``, ``tools``, ``memory``), the ``{task: str}`` fallback when none
remain — and the per-call policy
:class:`~pirn_agents.tools.agent_tool_call.AgentToolCall` applies: the
nesting cap, the shared budget meter, the pooled provider.

``AgentTool`` is therefore a :class:`~pirn_agents.tools.tool_factory.ToolFactory`
whose knot class is ``AgentToolCall``: one call constructs
``AgentToolCall(arguments=..., agent_class=type(agent), bound=<the agent's
literal inputs>, ...)``, whose inner sink is a fresh instance of the agent
class.  ``name`` and ``description`` default from the agent but are
overridable; ``parameters`` derive from the agent's ``input_json_schema()``.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.ok import Ok
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.agent.agent_response_mapper import AgentResponseMapper
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.tools.agent_tool_call import AgentToolCall
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_declaration import ToolDeclaration
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.types.messaging.agent_response import AgentResponse


class AgentTool(ToolFactory):
    """A tool capability that runs a wrapped :class:`SubTapestry` agent per call."""

    #: Conventional names of injected collaborators an agent's ``process``
    #: declares; never caller-facing, so never declared to the model.
    _dependency_names: ClassVar[frozenset[str]] = frozenset(
        {
            "llm",
            "tools",
            "tool",
            "search_tool",
            "specialists",
            "memory",
            "memory_store",
            "embedder",
            "embedding_provider",
            "provider",
            "messages",
        }
    )

    def __init__(
        self,
        agent: SubTapestry,
        *,
        name: str | None = None,
        description: str | None = None,
        input_schema: Mapping[str, Any] | None = None,
        provider: LLMProvider | None = None,
        budget: RunBudget | None = None,
        max_depth: int = 8,
    ) -> None:
        """Wrap ``agent`` as a tool capability.

        Args:
            agent: The ``SubTapestry`` agent to expose; its literal inputs are
                bound for every call.
            name: Tool name; defaults to the agent's snake_case class name.
            description: Tool description; defaults to the agent's docstring.
            input_schema: Explicit JSON-Schema ``parameters`` object; derived
                from the agent's ``process`` signature when omitted.
            provider: A pooled provider nested agents should reuse.
            budget: A budget enforced across this tool's (possibly nested) run.
            max_depth: Maximum agent-as-tool nesting depth (8 by default);
                enforced by core's ``RunNesting`` guard.

        Raises:
            TypeError: If ``agent`` is not a ``SubTapestry`` or ``max_depth`` is
                not a positive int.
        """
        if not isinstance(agent, SubTapestry):
            raise TypeError(f"AgentTool: agent must be a SubTapestry, got {type(agent).__name__}")
        if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth <= 0:
            raise TypeError(f"AgentTool: max_depth must be a positive int, got {max_depth!r}")
        template = ToolFactory.from_knot(agent)
        agent_name = name if name is not None else template.name
        super().__init__(
            AgentToolCall,
            name=agent_name,
            description=description if description is not None else template.description,
            parameters=input_schema,
        )
        self._agent = agent
        self._agent_bound: dict[str, Any] = dict(template.bound)
        self._provider = provider
        self._budget = budget
        self._max_depth = max_depth

    @property
    def agent(self) -> SubTapestry:
        """The wrapped agent."""
        return self._agent

    def declaration(self) -> ToolDeclaration:
        """The agent's caller-facing inputs, or the conventional ``{task: str}`` schema."""
        if self._parameters is not None:
            return ToolDeclaration(
                name=self.name,
                description=self.description,
                parameters=copy.deepcopy(self._parameters),
            )
        schema = type(self._agent).input_json_schema()
        hidden = self._dependency_names
        properties = {
            k: dict(v) if isinstance(v, Mapping) else v
            for k, v in schema.get("properties", {}).items()
            if k not in hidden
        }
        if not properties:
            return ToolDeclaration(
                name=self.name, description=self.description, parameters=self.default_schema()
            )
        # The wrapped agent's own literal inputs are what a call falls back to
        # when the model omits them: declared as defaults, never hidden.
        for key, value in self._agent_bound.items():
            if key in properties and isinstance(properties[key], dict) and self._is_json(value):
                properties[key]["default"] = value
        parameters: dict[str, Any] = {"type": "object", "properties": properties}
        required = [
            k for k in schema.get("required", []) if k not in hidden and k not in self._agent_bound
        ]
        if required:
            parameters["required"] = required
        if "$defs" in schema:
            parameters["$defs"] = schema["$defs"]
        return ToolDeclaration(name=self.name, description=self.description, parameters=parameters)

    @staticmethod
    def _is_json(value: Any) -> bool:
        """Whether *value* can be shown as a JSON ``default``."""
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return False
        return True

    @staticmethod
    def default_schema() -> dict[str, Any]:
        """The conventional single-``task`` schema for an input-less agent."""
        return {
            "type": "object",
            "properties": {"task": {"type": "string"}},
            "required": ["task"],
        }

    def resolve_arguments(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Alias a ReAct-style ``input`` onto the primary parameter; ``call_id`` is not an input."""
        return super().resolve_arguments({k: v for k, v in arguments.items() if k != "call_id"})

    def validate_arguments(self, arguments: Mapping[str, Any]) -> dict[str, str]:
        """Only a missing required input is refused; the agent validates the rest itself."""
        return {
            key: reason
            for key, reason in super().validate_arguments(arguments).items()
            if reason == "missing_required"
        }

    def __call__(self, **kwargs: Any) -> Knot:
        """Construct one call: an :class:`AgentToolCall` over the wrapped agent's class."""
        framework = {key: kwargs.pop(key) for key in tuple(Knot.reserved_kwargs()) if key in kwargs}
        return AgentToolCall(
            arguments=kwargs,
            agent_class=type(self._agent),
            tool_name=self.name,
            agent_id=self._agent.knot_id,
            bound=self._agent_bound,
            budget=self._budget,
            provider=self._provider,
            max_depth=self._max_depth,
            **framework,
        )

    async def run_view(self, arguments: Mapping[str, Any]) -> ToolResult:
        """Run one call outside the engine and return its ``ToolResult`` view."""
        call_id = arguments.get("call_id")
        call = ToolCall(
            tool_name=self.name,
            arguments=dict(arguments),
            call_id=call_id if isinstance(call_id, str) and call_id else f"{self.name}-call",
        )
        outcome = await self.run_call(call)
        tokens: int | None = None
        if isinstance(outcome, Ok) and isinstance(outcome.value, AgentResponse):
            tokens = AgentResponseMapper().summarise_tokens(outcome.value.usage)
        return ToolResult.from_result(call.call_id, outcome, tokens=tokens)

    def _clear_credentials(self) -> None:
        """Drop the pooled provider reference held for nested reuse."""
        self._provider = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "agent": type(self._agent).__qualname__,
            "agent_id": self._agent.knot_id,
        }

    def __repr__(self) -> str:
        return f"<AgentTool name={self.name!r} agent={type(self._agent).__name__}>"
