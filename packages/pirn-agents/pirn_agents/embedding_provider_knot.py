"""``EmbeddingProviderKnot`` — vending Knot for an :class:`EmbeddingProvider`.

Wraps an externally-constructed embedding provider so it participates in the
pirn graph with full lineage. Because the provider is constructed once by the
caller and merely passed through the graph, every downstream consumer reuses
the same pooled client for the entire run (the pooling lever, AD-3).

Algorithm:
    1. Accept the provider value (resolved by the framework from an upstream
       Knot or a scalar passed at pipeline-build time).
    2. Return it unchanged so downstream Knots receive the same provider
       instance.

References:
    - :class:`pirn.core.providers.embedding_provider.EmbeddingProvider`
    - :class:`pirn_agents.llm_provider_knot.LLMProviderKnot` (the template).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider


class EmbeddingProviderKnot(Knot):
    """Vending Knot that passes an :class:`EmbeddingProvider` through the graph."""

    def __init__(
        self, *, provider: Knot | EmbeddingProvider, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(provider=provider, _config=_config, **kwargs)

    async def process(self, provider: EmbeddingProvider, **_: Any) -> EmbeddingProvider:
        """Return the provider unchanged.

        Args:
            provider: The embedding provider instance to pass through.

        Returns:
            The provider instance unchanged so it is reused across the run.
        """
        return provider
