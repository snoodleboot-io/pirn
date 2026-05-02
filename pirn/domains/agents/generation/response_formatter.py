"""``ResponseFormatter`` — render an :class:`AgentResponse` for end-user display."""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class ResponseFormatter(Knot):
    """Serialises an :class:`AgentResponse` into ``"plain"``, ``"markdown"`` or ``"json"``.

    The output is a plain string ready to surface to the end user (or
    persist to a log). ``json`` emits the full audit dict; ``markdown``
    wraps tool calls into a fenced block; ``plain`` returns just the
    response content.
    """

    supported_formats: ClassVar[tuple[str, ...]] = ("plain", "markdown", "json")

    def __init__(
        self,
        *,
        response: Knot,
        _config: KnotConfig,
        format: str = "plain",
        **kwargs: Any,
    ) -> None:
        if format not in type(self).supported_formats:
            raise ValueError(
                "ResponseFormatter: format must be one of "
                f"{type(self).supported_formats!r}, got {format!r}"
            )
        super().__init__(
            response=response,
            format=format,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        format: str,
        **_: Any,
    ) -> str:
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "ResponseFormatter: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        if format == "plain":
            return response.content
        if format == "markdown":
            return self._render_markdown(response)
        return json.dumps(response._pirn_audit_dict(), sort_keys=True)

    def _render_markdown(self, response: AgentResponse) -> str:
        sections: list[str] = [response.content] if response.content else []
        if response.tool_calls:
            sections.append("\n**Tool calls:**\n")
            for call in response.tool_calls:
                sections.append(
                    f"- `{call.tool_name}` (`{call.call_id}`): "
                    f"{json.dumps(dict(call.arguments), sort_keys=True)}"
                )
        return "\n".join(sections)
