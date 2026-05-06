"""``ElandSource`` — Tier-4 source Knot that opens an Elasticsearch index
through an ``eland.DataFrame``.

The Elasticsearch client is supplied via an :class:`ElasticsearchConnectionKnot`
upstream, which wraps the live ``elasticsearch.Elasticsearch`` client. The
actual ``eland`` import happens inside :meth:`process` so this module imports
cleanly even when ``eland`` is not installed.

Algorithm:
    1. Receive the resolved :class:`ElasticsearchConnection` wrapper and an
       index name string from upstream Knots.
    2. Validate that ``index`` is a non-empty string.
    3. Unwrap the Elasticsearch client via ``connection.client``.
    4. Import ``eland`` and construct an ``eland.DataFrame`` against the index.
    5. Wrap the frame in :class:`ElandDataFrame` with a ``source_uri`` of
       ``elasticsearch://<index>`` and return it.

References:
    [1] eland — pandas-like API for Elasticsearch:
        https://eland.readthedocs.io/
    [2] Elasticsearch Python client:
        https://www.elastic.co/guide/en/elasticsearch/client/python-api/current/index.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.specialized.eland.eland_dataframe import ElandDataFrame
from pirn.domains.data.specialized.eland.elasticsearch_connection import (
    ElasticsearchConnection,
)
from pirn.domains.data.specialized.eland.elasticsearch_connection_knot import (
    ElasticsearchConnectionKnot,
)
from pirn.nodes.source import Source


class ElandSource(Source):
    """Open an ES index through eland and emit an :class:`ElandDataFrame`."""

    def __init__(
        self,
        *,
        connection: ElasticsearchConnectionKnot,
        index: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(connection=connection, index=index, _config=_config, **kwargs)

    async def process(
        self,
        *,
        connection: ElasticsearchConnection,
        index: str,
        **_: Any,
    ) -> ElandDataFrame:
        """Open the Elasticsearch index through eland and return an ElandDataFrame.

        Args:
            connection: Resolved :class:`ElasticsearchConnection` wrapping the
                Elasticsearch client.
            index: Name of the Elasticsearch index to open.

        Returns:
            An :class:`ElandDataFrame` wrapping the eland DataFrame.

        Raises:
            ValueError: If ``index`` is empty or not a string.
        """
        if not isinstance(index, str) or not index:
            raise ValueError("ElandSource: index must be a non-empty string")
        import eland as ed

        es_client = connection.client
        frame = ed.DataFrame(es_client=es_client, es_index_pattern=index)
        return ElandDataFrame(frame=frame, source_uri=f"elasticsearch://{index}")
