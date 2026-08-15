"""``SqlConnectorKnot`` — vending Knot for a pooled :class:`SqlConnector`.

Vends a SQL connector once per run (AD-3): the connector holds a single pooled
connection/pool that is built once and reused for the whole run (the pooling
lever).

The vended type is the :class:`~pirn_agents.tools.sql.sql_connector.SqlConnector`
*interface*, not a concrete connector. Since PIR-786 the shipped
:class:`~pirn_agents.connectors.sql_service_connector.SqlServiceConnector`
declares that interface, so it still flows through unchanged — but a second
backend (a test double, a different driver) no longer has to subclass the
concrete connector to be vendable, and downstream consumers depend on the
abstraction rather than the implementation.

A wrongly-typed value is rejected by the framework's ``validate_io`` at the IO
boundary (``SqlConnector`` derives from ``PirnOpaqueValue`` and supplies the
pydantic ``is_instance`` schema), so no per-knot ``isinstance`` guard is needed —
matching core's canonical vending knots.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.tools.sql.sql_connector import SqlConnector


class SqlConnectorKnot(Knot):
    """Vending Knot that passes a pooled :class:`SqlConnector` through the graph."""

    def __init__(
        self, *, connector: Knot | SqlConnector, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(connector=connector, _config=_config, **kwargs)

    async def process(self, connector: SqlConnector, **_: Any) -> SqlConnector:
        """Return the SQL connector unchanged.

        Args:
            connector: The SQL connector instance to pass through.

        Returns:
            The connector instance unchanged.
        """
        return connector
