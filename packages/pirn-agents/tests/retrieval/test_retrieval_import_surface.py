"""Characterization of the WS5/S4 (PIR-701) retrieval umbrella import surface.

S4 is a behavior-preserving refactor that ``git mv``\\s the flat retrieval-family
root modules of ``pirn_agents`` under a single ``retrieval`` umbrella package
(``retrieval.rerank``, ``retrieval.vector_stores``, ``retrieval.embeddings``,
``retrieval.graph_stores``, ``retrieval.graph_rag``), while a handful of modules
stay at the ``retrieval`` root.  This test pins the *post-move* public import
surface: every symbol listed below must be importable at its NEW module path,
and every OLD flat path must no longer resolve.

Imports are performed with :func:`importlib.import_module` inside the test
bodies (not at module top) so this file always COLLECTS cleanly even before the
parent's moves land -- only the assertions fail until the refactor completes.
"""

from __future__ import annotations

import importlib

import pytest

# (new_module_path, public_symbol_name) rows that the S4 move must satisfy.
# One row per entry in the frozen S4 final import contract.
_S4_IMPORT_SURFACE: list[tuple[str, str]] = [
    # rerank subpackage
    ("pirn_agents.retrieval.rerank.reranker_backend", "RerankerBackend"),
    ("pirn_agents.retrieval.rerank.cross_encoder_reranker", "CrossEncoderReranker"),
    # vector_stores subpackage
    ("pirn_agents.retrieval.vector_stores.vector_memory_store", "VectorMemoryStore"),
    ("pirn_agents.retrieval.vector_stores.in_memory_vector_store", "InMemoryVectorStore"),
    ("pirn_agents.retrieval.vector_stores.vector_record", "VectorRecord"),
    ("pirn_agents.retrieval.vector_stores.knots.vector_store_knot", "VectorStoreKnot"),
    # embeddings subpackage
    ("pirn_agents.retrieval.embeddings.embedding_provider", "EmbeddingProvider"),
    ("pirn_agents.retrieval.embeddings.base_embedding_provider", "BaseEmbeddingProvider"),
    (
        "pirn_agents.retrieval.embeddings.knots.embedding_provider_knot",
        "EmbeddingProviderKnot",
    ),
    # graph_stores subpackage
    ("pirn_agents.retrieval.graph_stores.graph_store", "GraphStore"),
    ("pirn_agents.retrieval.graph_stores.in_memory_graph_store", "InMemoryGraphStore"),
    # graph_rag subpackage
    ("pirn_agents.retrieval.graph_rag.hybrid_graph_retriever", "HybridGraphRetriever"),
    ("pirn_agents.retrieval.graph_rag.node_embedding_index", "NodeEmbeddingIndex"),
    # stays at the retrieval root
    ("pirn_agents.retrieval.bm25_index", "Bm25Index"),
    ("pirn_agents.retrieval.reciprocal_rank_fusion", "reciprocal_rank_fusion"),
    ("pirn_agents.retrieval.hybrid_retriever", "HybridRetriever"),
    # NEW shared base introduced by S4
    ("pirn_agents.retrieval.hybrid_retriever_base", "HybridRetrieverBase"),
]

# OLD flat module paths that S4 removes -- these must no longer import.
_S4_REMOVED_MODULES: list[str] = [
    "pirn_agents.rerank.reranker_backend",
    "pirn_agents.vector_stores.vector_memory_store",
    "pirn_agents.embeddings.embedding_provider",
    "pirn_agents.graph_rag.hybrid_graph_retriever",
    "pirn_agents.graph_stores.graph_store",
    "pirn_agents.vector_store_knot",
    "pirn_agents.embedding_provider_knot",
]


@pytest.mark.parametrize(
    ("module_path", "symbol_name"),
    _S4_IMPORT_SURFACE,
    ids=[f"{module}:{symbol}" for module, symbol in _S4_IMPORT_SURFACE],
)
def test_symbol_importable_at_new_path(module_path: str, symbol_name: str) -> None:
    """Every frozen-contract symbol must resolve at its post-move module path."""
    module = importlib.import_module(module_path)
    symbol = getattr(module, symbol_name)
    assert symbol is not None


@pytest.mark.parametrize("module_path", _S4_REMOVED_MODULES, ids=_S4_REMOVED_MODULES)
def test_old_flat_path_no_longer_imports(module_path: str) -> None:
    """Every pre-move flat module path must be gone after the S4 umbrella move."""
    with pytest.raises((ModuleNotFoundError, ImportError)):
        importlib.import_module(module_path)
