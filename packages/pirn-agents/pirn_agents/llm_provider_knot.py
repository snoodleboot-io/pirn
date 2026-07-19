"""``LLMProviderKnot`` — vending Knot for a :class:`LLMProvider`.

Wraps an externally-constructed provider so it participates in the pirn graph
with full lineage. Consumers receive the resolved provider value in their
``process()`` calls.

Algorithm:
    1. Accept the provider value (resolved by the framework from an upstream
       Knot or a scalar passed at pipeline-build time).
    2. Return it unchanged so downstream Knots receive the provider instance.


References:
    - :class:`pirn_agents.llm_provider.LLMProvider`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider


class LLMProviderKnot(Knot):
    """Vending Knot that passes a :class:`LLMProvider` through the graph."""

    def __init__(self, *, provider: Knot | LLMProvider, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(provider=provider, _config=_config, **kwargs)

    async def process(self, provider: LLMProvider, **_: Any) -> LLMProvider:
        """Return the provider unchanged.

        Args:
            provider: The LLM provider instance to pass through.

        Returns:
            The provider instance unchanged.
        """
        return provider
