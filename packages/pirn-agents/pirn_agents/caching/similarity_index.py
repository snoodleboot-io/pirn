"""``SimilarityIndex`` — vended resource for a key -> embedding nearest-match scan.

ADR agents-speaks-core WS2 part 2: a nearest-match scan over embeddings needs
enumeration, which :class:`pirn.backends.base.data_store.DataStore`
deliberately does not expose (``put``/``get``/``has``/``scrub`` — keyed
lookups only, by design). This mirrors how a vector-store backend
(``VectorBackendClient`` and friends) is a vended
:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` resource rather than
being force-fit through a ``Knot`` or a ``DataStore``: it holds *only* what a
scan needs (the embeddings, keyed by the same ``content_hash`` string the
matched value is stored under elsewhere), never the value itself. "index =
resource, values = DataStore" — see
:class:`~pirn_agents.caching.semantic_result_cache.SemanticResultCache` and
:class:`~pirn_agents.caching.prompt_cache.PromptCache` for the two shapes
that compose this with a value store.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.evaluation.cosine_similarity import CosineSimilarity


class SimilarityIndex(PirnOpaqueValue):
    """An in-process ``content_hash`` key -> embedding index for a similarity scan."""

    _cosine: ClassVar[CosineSimilarity] = CosineSimilarity()

    def __init__(self) -> None:
        """Create an empty index."""
        self._vectors: dict[str, tuple[float, ...]] = {}

    def __len__(self) -> int:
        return len(self._vectors)

    def put(self, key: str, embedding: Sequence[float]) -> None:
        """Index ``embedding`` under ``key`` (the value's ``content_hash``)."""
        self._vectors[key] = tuple(float(x) for x in embedding)

    def discard(self, key: str) -> None:
        """Remove ``key`` from the index, if present (a no-op otherwise)."""
        self._vectors.pop(key, None)

    def best_match(self, query: Sequence[float], threshold: float) -> str | None:
        """Return the indexed key whose embedding best matches ``query``.

        Args:
            query: The query embedding.
            threshold: Minimum cosine similarity (0..1) to count as a match.

        Returns:
            The best-matching key at or above ``threshold``, or ``None`` if
            no indexed embedding clears it.
        """
        best_key: str | None = None
        best_similarity = threshold
        for key, vector in self._vectors.items():
            similarity = self._similarity(query, vector)
            if similarity >= best_similarity:
                best_key = key
                best_similarity = similarity
        return best_key

    def ranked_matches(self, query: Sequence[float], threshold: float) -> tuple[str, ...]:
        """Return every indexed key at or above ``threshold``, best match first.

        Unlike :meth:`best_match`, this does not assume the best-scoring
        candidate is usable — a caller with an extra validity check on the
        matched value (e.g. a TTL the index itself knows nothing about) walks
        this in order until it finds one that passes.
        """
        scored = [(self._similarity(query, vector), key) for key, vector in self._vectors.items()]
        above_threshold = [pair for pair in scored if pair[0] >= threshold]
        above_threshold.sort(key=lambda pair: pair[0], reverse=True)
        return tuple(key for _similarity, key in above_threshold)

    @classmethod
    def _similarity(cls, query: Sequence[float], vector: Sequence[float]) -> float:
        """Return the cosine similarity of ``query`` and ``vector``, or 0.0 if unequal length."""
        if len(query) != len(vector):
            return 0.0
        return cls._cosine.compute(query, vector)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"size": len(self._vectors)}
