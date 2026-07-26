"""Vending knots for the tools domain.

Nests the tool-client :class:`~pirn.core.knot.Knot` adapters under their domain
(mirroring core's ``connectors/knots/`` layout). Ships
:class:`~pirn_agents.tools.knots.tool_client_knot.ToolClientKnot`, the
pass-through knot that vends a pooled tool client through the graph. Importing
this subpackage pulls in no backend.
"""

from __future__ import annotations
