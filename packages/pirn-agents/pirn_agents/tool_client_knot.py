"""``ToolClientKnot`` — vending Knot for a pooled tool-client connector.

Wraps an externally-constructed tool client (an outbound API / SaaS connector)
so it participates in the pirn graph with full lineage. A tool client holds
live backend state — an HTTP session or connection pool — so it is modelled as
:class:`pirn_agents.connector_base.ConnectorBase`, the pooled-client
abstraction. Passing the connector through the graph means its backend client
is constructed once and reused for the whole run (the pooling lever, AD-3).

Algorithm:
    1. Accept the client value (resolved by the framework from an upstream Knot
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


class ToolClientKnot(Knot):
    """Vending Knot that passes a pooled tool-client connector through the graph."""

    def __init__(self, *, client: Knot | ConnectorBase, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(client=client, _config=_config, **kwargs)

    async def process(self, client: ConnectorBase, **_: Any) -> ConnectorBase:
        """Return the tool client unchanged.

        Args:
            client: The tool-client connector instance to pass through.

        Returns:
            The connector instance unchanged so its pooled client is reused
            across the run.
        """
        return client
