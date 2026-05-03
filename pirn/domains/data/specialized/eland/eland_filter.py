"""``ElandFilter`` — Tier-4 row predicate that defers to eland for push-down.

Eland frames support a Pandas-shaped boolean-mask indexer that compiles
to an Elasticsearch ``bool`` query under the hood, so the filter runs in
the cluster rather than in Python. This knot takes a callable
``predicate(frame) -> mask`` and returns a new :class:`ElandDataFrame`
wrapping the filtered eland frame.

Common pattern::

    ElandFilter(
        frame=upstream,
        predicate=lambda df: df["status"] == "active",
        _config=KnotConfig(id="active_only"),
    )
"""

from __future__ import annotations

from typing import Any, Callable

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.specialized.eland.eland_dataframe import ElandDataFrame


class ElandFilter(Knot):
    """Apply a callable predicate to an :class:`ElandDataFrame`."""

    def __init__(
        self,
        *,
        frame: Knot,
        predicate: Callable[[Any], Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not callable(predicate):
            raise TypeError(
                "ElandFilter: predicate must be a callable "
                "(eland.DataFrame) -> mask; for row-by-row Python "
                "callables consider materialising via ElandToPandas first"
            )
        self._predicate = predicate
        super().__init__(frame=frame, _config=_config, **kwargs)

    @property
    def predicate(self) -> Callable[[Any], Any]:
        return self._predicate

    async def process(self, frame: ElandDataFrame, **_: Any) -> ElandDataFrame:
        """Apply the callable predicate to the eland frame and return a filtered ElandDataFrame.

        Args:
            frame: The upstream ElandDataFrame to filter.

        Returns:
            A new ElandDataFrame with the predicate applied as a push-down filter.
        """
        mask = self._predicate(frame.frame)
        filtered = frame.frame[mask]
        return ElandDataFrame(
            frame=filtered,
            source_uri=frame.source_uri,
            fetched_at=frame.fetched_at,
        )
