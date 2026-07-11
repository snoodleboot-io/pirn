"""Map an :class:`AgentResponse` into the F1 :class:`ToolResult` shape.

A nested agent invoked as a tool produces an :class:`AgentResponse` (content,
tool_calls, usage, cost). Callers of a :class:`~pirn_agents.tool.Tool` expect
the F1 :class:`~pirn_agents.types.tool_result.ToolResult` shape instead. This
module holds the single, shared translation so every agent-as-tool path maps
identically: the whole structured response is carried through as
``result`` (not just ``.content``), token usage is summarised onto ``tokens``,
and a successful turn is tagged :attr:`ToolStatus.OK`.
"""

from __future__ import annotations

from collections.abc import Mapping

from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


def summarise_tokens(usage: Mapping[str, int]) -> int | None:
    """Collapse a provider ``usage`` mapping to a single token count.

    Prefers an explicit ``total_tokens`` field; otherwise sums the
    ``input_tokens``/``output_tokens`` pair. Returns ``None`` when the mapping
    carries no recognised token fields so ``tokens`` stays unset rather than
    reporting a misleading zero.
    """
    if not usage:
        return None
    total = usage.get("total_tokens")
    if total is not None:
        return int(total)
    parts = [usage[key] for key in ("input_tokens", "output_tokens") if key in usage]
    if parts:
        return int(sum(parts))
    return None


def agent_response_to_tool_result(
    response: AgentResponse,
    *,
    call_id: str,
    latency: float | None = None,
) -> ToolResult:
    """Convert a successful :class:`AgentResponse` into a :class:`ToolResult`.

    The full ``response`` is passed through as :attr:`ToolResult.result` so a
    caller retains access to ``content``, ``tool_calls``, ``usage`` and
    ``cost`` — structured passthrough rather than a lossy ``.content`` string.
    ``tokens`` is derived from :attr:`AgentResponse.usage`.

    Args:
        response: The outcome of the nested agent turn.
        call_id: Identifier the originating tool call will reference back.
        latency: Wall-clock seconds the nested run took, when measured.

    Returns:
        An ``OK`` :class:`ToolResult` wrapping the structured response.
    """
    return ToolResult(
        call_id=call_id,
        result=response,
        status=ToolStatus.OK,
        latency=latency,
        tokens=summarise_tokens(response.usage),
    )
