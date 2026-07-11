"""``SearchConnectorKnot`` — vending Knot for a pooled :class:`SearchBackend`.

Vends the F16-S3 search connector once per run (AD-3): the provider-neutral
:class:`~pirn_agents.tools.web.search_backend.SearchBackend` (e.g. the generic
:class:`~pirn_agents.connectors.http_search_connector.HttpSearchConnector`) is
constructed once and passed through the graph unchanged, so any pooled client it
holds is reused for the whole run. ``process`` validates the vended value with an
``isinstance`` check so a mis-wired pipeline fails loudly at the vend site.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.tools.web.search_backend import SearchBackend


class SearchConnectorKnot(Knot):
    """Vending Knot that passes a pooled :class:`SearchBackend` through the graph."""

    def __init__(
        self, *, connector: Knot | SearchBackend, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(connector=connector, _config=_config, **kwargs)

    async def process(self, connector: SearchBackend, **_: Any) -> SearchBackend:
        """Return the search connector unchanged after validating its type.

        Raises:
            TypeError: If ``connector`` is not a :class:`SearchBackend`.
        """
        if not isinstance(connector, SearchBackend):
            raise TypeError(
                f"SearchConnectorKnot: expected a SearchBackend, got {type(connector).__name__}"
            )
        return connector
