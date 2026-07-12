"""GraphRAG knots over the provider-neutral :class:`GraphStore`.

Ships the schema-guided entity/relation extraction knot (built on the F20
structured-output contract), k-hop traversal + subgraph selection feeding a
:class:`~pirn_agents.graph_rag.graph_context_builder.GraphContextBuilder`,
node embedding generation over the F4 embedding interface, and a graph+vector
hybrid retriever that fuses graph-neighborhood and dense-vector rankings with
Reciprocal Rank Fusion. Importing this subpackage pulls in no external backend.
"""

from __future__ import annotations
