"""Lexical + hybrid retrieval primitives.

Ships a pure-Python Okapi BM25 lexical index (no external dependency, resolving
OD-2), a Reciprocal Rank Fusion helper, and a
:class:`~pirn_agents.retrieval.hybrid_retriever.HybridRetriever` knot that fuses
dense and lexical rankings. Importing this subpackage pulls in no backend.
"""

from __future__ import annotations
