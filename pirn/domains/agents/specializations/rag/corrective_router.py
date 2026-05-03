"""``CorrectiveRouter`` — fall back to a tool when retrieval comes up empty.

Inputs:
    relevant_docs: docs that survived a :class:`RelevanceGate`. When
        empty, the fallback tool is invoked with the query.
    query: the original user query.

Output: a ``list[Mapping[str, Any]]`` of "documents" that downstream
prompt-builder knots can format. Tool fallback wraps the tool result
in a single-doc list of the form ``[{"source": "fallback", "content": ...}]``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.tool import Tool


class CorrectiveRouter(Knot):
    """Forward relevant docs, or invoke ``fallback_tool`` when none qualify."""

    def __init__(
        self,
        *,
        query: Knot | str,
        relevant_docs: Knot,
        fallback_tool: Tool,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(fallback_tool, Tool):
            raise TypeError(
                "CorrectiveRouter: fallback_tool must be a Tool, "
                f"got {type(fallback_tool).__name__}"
            )
        self._fallback_tool = fallback_tool
        super().__init__(
            query=query,
            relevant_docs=relevant_docs,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        relevant_docs: list[Mapping[str, Any]],
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Return relevant_docs when non-empty, otherwise invoke the fallback tool and return its result.

        Args:
            query: The original user query used as input when the fallback tool is invoked.
            relevant_docs: The list of documents that survived the relevance gate.

        Returns:
            The relevant_docs list if non-empty, otherwise a single-entry list from the fallback tool.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                "CorrectiveRouter: query must be a string, "
                f"got {type(query).__name__}"
            )
        if relevant_docs:
            return list(relevant_docs)
        fallback_result = await self._fallback_tool.invoke({"input": query})
        return [{"source": "fallback", "content": str(fallback_result)}]
