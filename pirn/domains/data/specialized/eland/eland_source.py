"""``ElandSource`` — Tier-4 source knot that opens an Elasticsearch index
through an ``eland.DataFrame``.

Takes a live :class:`elasticsearch.Elasticsearch` client and an index
name; constructs the eland DataFrame at run time and emits an
:class:`ElandDataFrame` adapter. The actual ``eland`` import happens
inside :meth:`process` so this module imports cleanly even when
``eland`` is not installed.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.specialized.eland.eland_dataframe import ElandDataFrame
from pirn.nodes.source import Source


class ElandSource(Source):
    """Open an ES index through eland and emit an :class:`ElandDataFrame`."""

    def __init__(
        self,
        *,
        es_client: Any,
        index: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if es_client is None:
            raise ValueError(
                "ElandSource: es_client must be a live "
                "elasticsearch.Elasticsearch instance, not None"
            )
        if not isinstance(index, str) or not index:
            raise ValueError("ElandSource: index must be a non-empty string")
        self._es_client = es_client
        self._index = index
        super().__init__(_config=_config, **kwargs)

    @property
    def es_client(self) -> Any:
        return self._es_client

    @property
    def index(self) -> str:
        return self._index

    async def process(self, **_: Any) -> ElandDataFrame:
        """Open the configured Elasticsearch index through eland and return an ElandDataFrame.

        Returns:
            An ElandDataFrame wrapping the eland DataFrame for the configured index.
        """
        import eland as ed

        frame = ed.DataFrame(es_client=self._es_client, es_index_pattern=self._index)
        return ElandDataFrame(frame=frame, source_uri=f"elasticsearch://{self._index}")
