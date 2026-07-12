"""``QueryRouteClassifier`` — pick the best route for a query via the LLM.

The classification stage of Router RAG. Given a query and the set of available
route names, the LLM is asked to name the single most appropriate route; the
answer is matched back against the known names, falling back to the first route
when the reply is unrecognised.

Algorithm:
    1. Validate ``query`` (str), ``llm`` (:class:`LLMProvider`), and
       ``route_names`` (non-empty list of str).
    2. Prompt the LLM to choose exactly one route name.
    3. Match the reply case-insensitively against the known names (exact match
       first, then substring), returning the first known name it mentions.
    4. Fall back to ``route_names[0]`` when nothing matches.

References:
    - Jeong et al., "Adaptive-RAG" (2024): https://arxiv.org/abs/2403.14403
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class QueryRouteClassifier(Knot):
    """Classify a query to one of ``route_names`` using the LLM."""

    def __init__(
        self,
        *,
        query: Knot | str,
        llm: Knot | LLMProvider,
        route_names: Knot | list[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            llm=llm,
            route_names=route_names,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        llm: LLMProvider,
        route_names: list[str],
        **_: Any,
    ) -> str:
        """Return the chosen route name for ``query``.

        Args:
            query: The user query to classify.
            llm: The provider that selects the route.
            route_names: The available route names; must be non-empty.

        Returns:
            One of ``route_names`` — the LLM's choice, or ``route_names[0]`` on
            an unrecognised reply.

        Raises:
            TypeError: If ``query`` is not a string or ``llm`` is not an LLMProvider.
            ValueError: If ``route_names`` is empty.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"QueryRouteClassifier: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"QueryRouteClassifier: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not route_names:
            raise ValueError("QueryRouteClassifier: route_names must be non-empty")
        options = ", ".join(route_names)
        prompt = (
            "Choose the single most appropriate route for the query from this list: "
            f"{options}. Reply with only the route name.\n\nQuery: {query}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        reply = self._extract_text(raw).strip().lower()
        for name in route_names:
            if name.lower() == reply:
                return name
        for name in route_names:
            if name.lower() in reply:
                return name
        return route_names[0]

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
