"""``HttpConnectorKnot`` — vending Knot for a pooled :class:`HttpConnector`.

Vends the F16-S1 HTTP/REST connector once per run (AD-3): the connector is
constructed once by the caller and passed through the graph unchanged, so its
pooled ``httpx`` client is built a single time and reused for the whole run (the
pooling lever).

A wrongly-typed value is rejected by the framework's ``validate_io`` at the IO
boundary (``HttpConnector`` is a ``PirnOpaqueValue`` and supplies the pydantic
``is_instance`` schema), so no per-knot ``isinstance`` guard is needed — matching
core's canonical vending knots.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.connectors.http_connector import HttpConnector


class HttpConnectorKnot(Knot):
    """Vending Knot that passes a pooled :class:`HttpConnector` through the graph."""

    def __init__(
        self, *, connector: Knot | HttpConnector, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(connector=connector, _config=_config, **kwargs)

    async def process(self, connector: HttpConnector, **_: Any) -> HttpConnector:
        """Return the HTTP connector unchanged.

        Args:
            connector: The HTTP connector instance to pass through.

        Returns:
            The connector instance unchanged.
        """
        return connector
