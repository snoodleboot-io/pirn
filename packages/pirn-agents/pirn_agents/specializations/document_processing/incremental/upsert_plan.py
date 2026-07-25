"""``UpsertPlan`` — the diff a content-hash upsert computes (F25-S4 / PIR-623).

Comparing a document's freshly chunked content against the last-indexed manifest
yields this plan: which chunks are new/changed (and must be embedded), which are
unchanged (skipped — the whole point of incremental indexing), and which old
chunk hashes were removed (and must be deleted). Re-index cost therefore scales
with the size of :attr:`to_embed`, not with the corpus.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk


@dataclass(frozen=True)
class UpsertPlan(PirnOpaqueValue):
    """The new/unchanged/removed partition for one document's re-index.

    Attributes
    ----------
    doc_id:
        The document these deltas belong to.
    to_embed:
        Chunks whose content hash is new or changed — the only chunks embedded.
    unchanged_hashes:
        Content hashes already indexed and left untouched (no re-embed).
    removed_hashes:
        Previously indexed hashes no longer present — their records are deleted.
    manifest_hashes:
        The full ordered hash list to record as the document's new manifest.
    """

    doc_id: str
    to_embed: tuple[Chunk, ...]
    unchanged_hashes: tuple[str, ...]
    removed_hashes: tuple[str, ...]
    manifest_hashes: tuple[str, ...]

    @property
    def embedded_count(self) -> int:
        """Number of chunks that were (or will be) embedded."""
        return len(self.to_embed)

    @property
    def unchanged_count(self) -> int:
        """Number of already-indexed chunks skipped."""
        return len(self.unchanged_hashes)

    @property
    def removed_count(self) -> int:
        """Number of stale chunk records removed."""
        return len(self.removed_hashes)
