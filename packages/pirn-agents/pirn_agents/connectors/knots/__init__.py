"""Vending knots for the connector domain.

Nests the connector :class:`~pirn.core.knot.Knot` adapters under their domain
(mirroring core's ``connectors/knots/`` layout). Ships the pass-through knots
that vend a pooled connector through the graph:
:class:`~pirn_agents.connectors.knots.http_connector_knot.HttpConnectorKnot`,
:class:`~pirn_agents.connectors.knots.search_connector_knot.SearchConnectorKnot`,
and :class:`~pirn_agents.connectors.knots.sql_connector_knot.SqlConnectorKnot`.
Importing this subpackage pulls in no backend.
"""

from __future__ import annotations
