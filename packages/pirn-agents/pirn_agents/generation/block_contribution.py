"""``BlockContribution`` — a content block's contribution to a parsed response.

A small value object a :class:`ContentBlockHandler` returns when it recognises a
content block: either a text fragment to append, a :class:`ToolCall` to collect,
or both. :class:`OutputParser` aggregates these across all blocks into the final
:class:`AgentResponse`.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn_agents.tools.tool_call import ToolCall


@dataclass(frozen=True)
class BlockContribution:
    """A recognised block's text and/or tool-call contribution.

    Attributes
    ----------
    text:
        A text fragment to append to the response content, if any.
    tool_call:
        A :class:`ToolCall` to collect on the response, if any.
    """

    text: str | None = None
    tool_call: ToolCall | None = None
