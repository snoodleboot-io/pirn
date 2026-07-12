"""Provider-neutral knowledge-graph stores.

Ships the graph-native value types (:class:`~pirn_agents.graph_stores.graph_node.GraphNode`,
:class:`~pirn_agents.graph_stores.graph_edge.GraphEdge`,
:class:`~pirn_agents.graph_stores.graph_neighbor.GraphNeighbor`), the abstract
:class:`~pirn_agents.graph_stores.graph_store.GraphStore` contract, a
zero-dependency in-memory adjacency-list reference implementation, and lazy
Neo4j / Kuzu adapters behind the ``neo4j`` / ``kuzu`` extras. Importing this
subpackage pulls in no external backend.
"""

from __future__ import annotations
