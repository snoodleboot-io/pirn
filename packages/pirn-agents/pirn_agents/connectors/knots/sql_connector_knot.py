"""``SqlConnectorKnot`` — vending Knot for a pooled :class:`SqlServiceConnector`.

Vends the F16-S2 SQL connector once per run (AD-3): the connector holds a single
pooled connection/pool that is built once and reused for the whole run (the
pooling lever).

A wrongly-typed value is rejected by the framework's ``validate_io`` at the IO
boundary (``SqlServiceConnector`` is a ``PirnOpaqueValue`` and supplies the
pydantic ``is_instance`` schema), so no per-knot ``isinstance`` guard is needed —
matching core's canonical vending knots.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.connectors.sql_service_connector import SqlServiceConnector


class SqlConnectorKnot(Knot):
    """Vending Knot that passes a pooled :class:`SqlServiceConnector` through the graph."""

    def __init__(
        self, *, connector: Knot | SqlServiceConnector, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(connector=connector, _config=_config, **kwargs)

    async def process(self, connector: SqlServiceConnector, **_: Any) -> SqlServiceConnector:
        """Return the SQL connector unchanged.

        Args:
            connector: The SQL service connector instance to pass through.

        Returns:
            The connector instance unchanged.
        """
        return connector
