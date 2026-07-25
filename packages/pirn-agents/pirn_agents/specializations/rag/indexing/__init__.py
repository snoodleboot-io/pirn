"""Indexing-structure patterns for RAG (parent-doc, sentence-window, auto-merging, RAPTOR).

Each pattern is an ingest + retrieve knot pair that builds on the existing
:class:`~pirn_agents.specializations.document_processing._document_chunker._DocumentChunker`
and adds only the indexing-specific structure (parent-child links, sentence
windows, RAPTOR summary tree). It does not introduce a general chunking library.
"""

__all__: list[str] = []
