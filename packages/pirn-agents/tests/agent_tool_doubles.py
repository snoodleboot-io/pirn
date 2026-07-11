"""Stub ``SubTapestry`` agents used by the agents-as-tools (F7) tests.

These doubles run through the *real* ``SubTapestry`` machinery (an inner
tapestry with a ``Source`` sink) but need no LLM: each returns a canned
:class:`AgentResponse`. Invocations are recorded into module-level registries
(keyed by ``knot_id``) so a test can assert which provider a nested run reused
and how deep it ran — mirroring the ``_SPEC_REGISTRY`` pattern already used by
the orchestrator tests.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.agent_as_tool_mixin import AgentAsToolMixin
from pirn_agents.agent_tool_context import current_agent_tool_context
from pirn_agents.types.agent_response import AgentResponse

# knot_id -> list of {"topic": str, "llm": object, "depth": int}
AGENT_CALLS: dict[str, list[dict[str, Any]]] = {}
# knot_id -> AgentTool to hand off to next (None => leaf)
ROUTE_REGISTRY: dict[str, Any] = {}


def reset_doubles() -> None:
    """Clear the shared recording/routing registries between tests."""
    AGENT_CALLS.clear()
    ROUTE_REGISTRY.clear()


def _source_returning(response: AgentResponse) -> Source:
    """Build a ``Source`` sink whose output is ``response``."""

    class _ResultSource(Source):
        async def process(self, **_: Any) -> AgentResponse:
            return response

    return _ResultSource(_config=KnotConfig(id="out"))


class StubAgent(AgentAsToolMixin, SubTapestry):
    """Returns ``"{reply}:{topic}"``; records the ``topic``/``llm`` it ran with."""

    def __init__(
        self,
        *,
        topic: str = "",
        llm: Any = None,
        reply: str = "ok",
        fail: bool = False,
        usage: Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            topic=topic,
            llm=llm,
            reply=reply,
            fail=fail,
            usage=usage,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        topic: str = "",
        llm: Any = None,
        reply: str = "ok",
        fail: bool = False,
        usage: Any = None,
        **_: Any,
    ) -> Any:
        context = current_agent_tool_context()
        AGENT_CALLS.setdefault(self.knot_id, []).append(
            {"topic": topic, "llm": llm, "depth": context.depth if context else -1}
        )
        if fail:
            raise RuntimeError(f"boom:{topic}")
        return _source_returning(
            AgentResponse(content=f"{reply}:{topic}", usage=dict(usage) if usage else {})
        )


class NestingAgent(AgentAsToolMixin, SubTapestry):
    """Hands off to the ``AgentTool`` registered for its ``knot_id``.

    A leaf (no registered next tool) returns ``"leaf[<id>]@<depth>"``; otherwise
    it invokes the next tool and wraps the observation. Routing keyed on
    ``knot_id`` lets a test wire mutually-recursive graphs (``A`` → ``B`` → ``A``)
    after both agents are constructed.
    """

    def __init__(self, *, task: str = "", _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str = "", **_: Any) -> Any:
        me = self.knot_id
        context = current_agent_tool_context()
        depth = context.depth if context else -1
        AGENT_CALLS.setdefault(me, []).append({"topic": task, "llm": None, "depth": depth})
        next_tool = ROUTE_REGISTRY.get(me)
        if next_tool is None:
            response = AgentResponse(content=f"leaf[{me}]@{depth}")
        else:
            inner = await next_tool.invoke({"task": task})
            body = inner.result.content if inner.result is not None else inner.error
            response = AgentResponse(content=f"{me}@{depth}->{body}")
        return _source_returning(response)


class TopicMaxAgent(AgentAsToolMixin, SubTapestry):
    """Declares an explicit ``topic``/``max_results`` signature for schema tests."""

    def __init__(
        self,
        *,
        topic: str,
        max_results: int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(topic=topic, max_results=max_results, _config=_config, **kwargs)

    async def process(self, topic: str, max_results: int = 5, **_: Any) -> Any:
        return _source_returning(AgentResponse(content=f"{topic}:{max_results}"))


class NoInputAgent(AgentAsToolMixin, SubTapestry):
    """Declares no caller-facing inputs, exercising the ``{task: str}`` default."""

    def __init__(self, *, llm: Any = None, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(llm=llm, _config=_config, **kwargs)

    async def process(self, llm: Any = None, **_: Any) -> Any:
        return _source_returning(AgentResponse(content="fixed"))
