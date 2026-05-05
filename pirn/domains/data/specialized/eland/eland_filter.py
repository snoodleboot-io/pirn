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

Algorithm:
    1. Validate that ``predicate`` is callable.
    2. Invoke ``predicate(frame.frame)`` to obtain a boolean mask.
       The mask is a Pandas-style boolean Series that eland compiles to
       an Elasticsearch ``bool`` query at execution time.
    3. Apply the mask via ``frame.frame[mask]`` to produce a filtered
       eland DataFrame.
    4. Return a new :class:`ElandDataFrame` preserving the ``source_uri``
       and ``fetched_at`` provenance metadata from the upstream frame.

    ```text
    mask     = predicate(eland_frame)
    filtered = eland_frame[mask]
    return ElandDataFrame(frame=filtered, source_uri=..., fetched_at=...)
    ```

References:
    [1] eland — boolean indexing / push-down filtering:
        https://eland.readthedocs.io/en/latest/reference/filtering.html
    [2] Elasticsearch — bool query (compiled from eland boolean masks):
        https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.specialized.eland.eland_dataframe import ElandDataFrame


class ElandFilter(Knot):
    """Apply a callable predicate to an :class:`ElandDataFrame`."""

    def __init__(
        self,
        *,
        frame: Knot,
        predicate: Knot | Callable[[Any], Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(frame=frame, predicate=predicate, _config=_config, **kwargs)

    async def process(
        self,
        frame: ElandDataFrame,
        predicate: Any,  # Callable[[Any], Any] — pydantic can't schema Callable
        **_: Any,
    ) -> ElandDataFrame:
        """Apply the callable predicate to the eland frame and return a filtered ElandDataFrame.

        Args:
            frame: The upstream ElandDataFrame to filter.
            predicate: A callable ``(eland.DataFrame) -> mask`` applied for push-down filtering.

        Returns:
            A new ElandDataFrame with the predicate applied as a push-down filter.
        """
        if not callable(predicate):
            raise TypeError(
                "ElandFilter: predicate must be a callable "
                "(eland.DataFrame) -> mask; for row-by-row Python "
                "callables consider materialising via ElandToPandas first"
            )
        mask = predicate(frame.frame)
        filtered = frame.frame[mask]
        return ElandDataFrame(
            frame=filtered,
            source_uri=frame.source_uri,
            fetched_at=frame.fetched_at,
        )
