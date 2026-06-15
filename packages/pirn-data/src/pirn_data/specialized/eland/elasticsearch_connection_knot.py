"""``ElasticsearchConnectionKnot`` — vending Knot for :class:`ElasticsearchConnection`.

An ``elasticsearch.Elasticsearch`` client is a live, stateful object that
cannot travel through the pirn graph as a plain constructor argument
(R6 violation). This vending Knot receives a constructed client during
``process()`` and returns it wrapped in a pydantic-opaque
:class:`ElasticsearchConnection` so that consumer Knots can declare it as a
typed upstream dependency and receive the resolved wrapper in their own
``process()`` calls.

Share a single :class:`ElasticsearchConnectionKnot` across all Knots that
need to operate on the same Elasticsearch cluster.

Algorithm:
    1. Receive the caller-supplied Elasticsearch client (any object satisfying
       the ``elasticsearch.Elasticsearch`` interface).
    2. Wrap it in :class:`ElasticsearchConnection` for pydantic compatibility.
    3. Return the wrapper so downstream Knots receive it as a resolved value.

References:
    [1] Elasticsearch Python client:
        https://www.elastic.co/guide/en/elasticsearch/client/python-api/current/index.html
    [2] eland — pandas-like API for Elasticsearch:
        https://eland.readthedocs.io/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.specialized.eland.elasticsearch_connection import (
    ElasticsearchConnection,
)


class ElasticsearchConnectionKnot(Knot):
    """Construct and vend an :class:`ElasticsearchConnection`.

    Pass a live Elasticsearch client as ``es_client``. Downstream Knots
    declare this Knot as a typed ``__init__`` parameter and receive the
    :class:`ElasticsearchConnection` wrapper in ``process()``.
    """

    def __init__(self, *, es_client: Knot | Any, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(es_client=es_client, _config=_config, **kwargs)

    async def process(self, *, es_client: Any, **_: Any) -> ElasticsearchConnection:
        """Wrap the supplied Elasticsearch client in an :class:`ElasticsearchConnection`.

        Args:
            es_client: A live Elasticsearch client instance.

        Returns:
            An :class:`ElasticsearchConnection` wrapping the client.
        """
        return ElasticsearchConnection(client=es_client)
