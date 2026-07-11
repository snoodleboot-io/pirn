"""``SqlConnectorKnot`` — vending Knot for a pooled :class:`SqlServiceConnector`.

Vends the F16-S2 SQL connector once per run (AD-3): the connector holds a single
pooled connection/pool that is built once and reused for the whole run (the
pooling lever). ``process`` validates the vended value with an ``isinstance``
check so a mis-wired pipeline fails loudly at the vend site.
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
        """Return the SQL connector unchanged after validating its type.

        Raises:
            TypeError: If ``connector`` is not a :class:`SqlServiceConnector`.
        """
        if not isinstance(connector, SqlServiceConnector):
            raise TypeError(
                f"SqlConnectorKnot: expected a SqlServiceConnector, got {type(connector).__name__}"
            )
        return connector
