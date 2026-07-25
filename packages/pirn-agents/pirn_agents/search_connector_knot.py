"""``SearchConnectorKnot`` — vending Knot for a pooled :class:`SearchBackend`.

Vends the F16-S3 search connector once per run (AD-3): the provider-neutral
:class:`~pirn_agents.tools.web.search_backend.SearchBackend` (e.g. the generic
:class:`~pirn_agents.connectors.http_search_connector.HttpSearchConnector`) is
constructed once and passed through the graph unchanged, so any pooled client it
holds is reused for the whole run.

A wrongly-typed value is rejected by the framework's ``validate_io`` at the IO
boundary (``SearchBackend`` is a ``PirnOpaqueValue`` and supplies the pydantic
``is_instance`` schema), so no per-knot ``isinstance`` guard is needed — matching
core's canonical vending knots.
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
        """Return the search connector unchanged.

        Args:
            connector: The search backend instance to pass through.

        Returns:
            The connector instance unchanged.
        """
        return connector
