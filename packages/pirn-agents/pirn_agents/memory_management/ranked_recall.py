"""``RankedRecall`` — fuse relevance, recency, and importance into a recall order.

The S4 ranking knot. It takes candidates the retrieval layer already scored
(:class:`~pirn_agents.memory_management.recall_candidate.RecallCandidate`) and
ranks them by a configurable composite of three signals:

* **relevance** — each candidate's raw query-relevance from F4 hybrid retrieval,
  or, when an optional rerank hook is supplied, that hook's score;
* **recency** — a half-life decay of the record's recency anchor;
* **importance** — the record's caller-assigned importance.

Each signal is min-max normalised across the candidate set into ``[0, 1]`` so the
:class:`~pirn_agents.memory_management.recall_weights.RecallWeights` — not the
signals' native scales — govern their influence, then fused as
``w_rel·rel + w_rec·rec + w_imp·imp``. Results are returned as
:class:`~pirn_agents.memory_management.ranked_memory.RankedMemory` in descending
score (ties broken by record id for determinism).

Rerank hook (provider-neutral)
------------------------------
``reranker`` is an optional
:class:`~pirn_agents.rerank.reranker_backend.RerankerBackend` — the F4 protocol.
When ``None`` (the default) recall uses the candidates' own relevance, so no
vendor is favoured and no backend is imported; when supplied, any cross-encoder,
LLM scorer, or stub is interchangeable behind the protocol.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory_management.decay_function import decay_score
from pirn_agents.memory_management.memory_record import MemoryRecord
from pirn_agents.memory_management.ranked_memory import RankedMemory
from pirn_agents.memory_management.recall_candidate import RecallCandidate
from pirn_agents.memory_management.recall_weights import RecallWeights
from pirn_agents.rerank.reranker_backend import RerankerBackend


class RankedRecall(Knot):
    """Ranks recall candidates by a weighted relevance/recency/importance blend."""

    def __init__(
        self,
        *,
        query: Knot | str,
        candidates: Knot | Sequence[RecallCandidate],
        now: Knot | datetime,
        weights: Knot | RecallWeights | None = None,
        reranker: Knot | Any | None = None,
        half_life_seconds: Knot | float = 86400.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            candidates=candidates,
            now=now,
            weights=weights,
            reranker=reranker,
            half_life_seconds=half_life_seconds,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        candidates: Sequence[RecallCandidate],
        now: datetime,
        weights: RecallWeights | None = None,
        reranker: Any = None,
        half_life_seconds: float = 86400.0,
        **_: Any,
    ) -> list[RankedMemory]:
        """Return ``candidates`` ranked by the fused composite score.

        Args:
            query: The recall query (used only by an optional reranker).
            candidates: The scored candidates to rank.
            now: The timezone-aware reference time for recency.
            weights: Signal weights; defaults to an equal :class:`RecallWeights`.
            reranker: Optional F4 rerank backend; ``None`` uses candidate
                relevance.
            half_life_seconds: Recency half-life in seconds; must be positive.

        Returns:
            :class:`RankedMemory` results in descending composite score.

        Raises:
            TypeError: If a candidate is not a RecallCandidate, ``weights`` is not
                a RecallWeights, ``reranker`` is not a RerankerBackend, or ``now``
                is not a datetime.
        """
        weights = weights if weights is not None else RecallWeights()
        if not isinstance(weights, RecallWeights):
            raise TypeError(
                f"RankedRecall: weights must be a RecallWeights, got {type(weights).__name__}"
            )
        if not isinstance(now, datetime):
            raise TypeError(f"RankedRecall: now must be a datetime, got {type(now).__name__}")
        if reranker is not None and not isinstance(reranker, RerankerBackend):
            raise TypeError(
                f"RankedRecall: reranker must be a RerankerBackend or None, "
                f"got {type(reranker).__name__}"
            )
        items = tuple(self._require_candidate(candidate) for candidate in candidates)
        if not items:
            return []
        records = [candidate.record for candidate in items]
        relevance_raw = await self._relevance(query, items, reranker)
        recency_raw = [self._recency(record, now, half_life_seconds) for record in records]
        importance_raw = [float(record.importance) for record in records]
        relevance = self._min_max(relevance_raw)
        recency = self._min_max(recency_raw)
        importance = self._min_max(importance_raw)
        ranked = [
            RankedMemory(
                record=records[index],
                score=(
                    weights.relevance * relevance[index]
                    + weights.recency * recency[index]
                    + weights.importance * importance[index]
                ),
                relevance=relevance[index],
                recency=recency[index],
                importance=importance[index],
            )
            for index in range(len(records))
        ]
        ranked.sort(key=lambda item: (-item.score, item.record.id))
        return ranked

    @staticmethod
    def _require_candidate(candidate: RecallCandidate) -> RecallCandidate:
        """Return ``candidate`` after asserting it is a :class:`RecallCandidate`."""
        if not isinstance(candidate, RecallCandidate):
            raise TypeError(
                f"RankedRecall: every candidate must be a RecallCandidate, "
                f"got {type(candidate).__name__}"
            )
        return candidate

    @staticmethod
    async def _relevance(
        query: str,
        items: Sequence[RecallCandidate],
        reranker: RerankerBackend | None,
    ) -> list[float]:
        """Return the raw relevance per candidate, from the reranker or candidates."""
        if reranker is None:
            return [float(candidate.relevance) for candidate in items]
        documents = [
            {"id": candidate.record.id, "content": candidate.record.content} for candidate in items
        ]
        scores = await reranker.score(query, documents)
        return [float(score) for score in scores]

    @staticmethod
    def _recency(record: MemoryRecord, now: datetime, half_life_seconds: float) -> float:
        """Return the half-life recency weight of ``record`` at ``now`` in ``[0, 1]``."""
        age_seconds = (now - record.recency_anchor()).total_seconds()
        return decay_score(1.0, age_seconds, half_life_seconds)

    @staticmethod
    def _min_max(values: Sequence[float]) -> list[float]:
        """Min-max normalise ``values`` into ``[0, 1]`` (all-equal → all ``0``)."""
        lowest = min(values)
        highest = max(values)
        span = highest - lowest
        if span == 0:
            return [0.0 for _ in values]
        return [(value - lowest) / span for value in values]
