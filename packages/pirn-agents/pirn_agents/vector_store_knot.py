"""``VectorStoreKnot`` — vending Knot for a pooled vector-store connector.

Wraps an externally-constructed vector-store client so it participates in the
pirn graph with full lineage. pirn-core exposes no dedicated ``VectorStore``
interface, so this knot vends the general pooled-client abstraction
:class:`pirn_agents.connector_base.ConnectorBase` — the natural type for a
vector-store backend whose live client (an HTTP session or database pool) must
be constructed once and reused. Passing the connector through the graph means
its backend client is built a single time and shared for the whole run (the
pooling lever, AD-3).

Algorithm:
    1. Accept the store value (resolved by the framework from an upstream Knot
       or a scalar passed at pipeline-build time).
    2. Return it unchanged so downstream Knots receive the same connector
       instance.

References:
    - :class:`pirn_agents.connector_base.ConnectorBase`
    - :class:`pirn_agents.llm_provider_knot.LLMProviderKnot` (the template).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.connector_base import ConnectorBase


class VectorStoreKnot(Knot):
    """Vending Knot that passes a pooled vector-store connector through the graph."""

    def __init__(self, *, store: Knot | ConnectorBase, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(store=store, _config=_config, **kwargs)

    async def process(self, store: ConnectorBase, **_: Any) -> ConnectorBase:
        """Return the store connector unchanged.

        Args:
            store: The vector-store connector instance to pass through.

        Returns:
            The connector instance unchanged so its pooled client is reused
            across the run.
        """
        return store
