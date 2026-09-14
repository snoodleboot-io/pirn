"""``MergeHits`` — union this round's hits into the accumulated set."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MergeHits(Knot):
    """Union this round's hits into the accumulated, deduplicated set."""

    def __init__(
        self,
        *,
        prior_merged: Knot | Mapping[str, Mapping[str, Any]],
        hits: Knot | list[Mapping[str, Any]],
        iteration: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prior_merged=prior_merged, hits=hits, iteration=iteration, _config=_config, **kwargs
        )

    async def process(
        self,
        prior_merged: Mapping[str, Mapping[str, Any]],
        hits: list[Mapping[str, Any]],
        iteration: int,
        **_: Any,
    ) -> dict[str, Mapping[str, Any]]:
        """Merge ``hits`` into ``prior_merged``, keeping the first-seen mapping.

        Args:
            prior_merged: The accumulated set from earlier rounds.
            hits: This round's freshly retrieved hits.
            iteration: The current round index, recorded on newly-seen hits.

        Returns:
            The updated accumulated set.
        """
        merged = dict(prior_merged)
        for hit in hits:
            key = MergeHits._doc_key(hit)
            if key not in merged:
                enriched = dict(hit)
                enriched.setdefault("iteration", iteration)
                merged[key] = enriched
        return merged

    @staticmethod
    def _doc_key(hit: Mapping[str, Any]) -> str:
        """Return a stable identity key for a retrieved hit."""
        identifier = hit.get("id")
        if identifier is not None:
            return str(identifier)
        return repr(sorted((str(k), str(v)) for k, v in hit.items()))
