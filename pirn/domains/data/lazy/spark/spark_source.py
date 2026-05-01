"""``SparkSource`` — pirn :class:`Source` that emits a deferred
:class:`SparkDataFrame`.

Two construction modes:

1. ``path`` (+ optional ``format`` / ``options``) — the source calls
   ``session.read.format(format).options(**options).load(path)``.
2. ``query`` — the source calls ``session.sql(query)`` to produce a
   deferred frame from a SQL statement (catalog tables / temp views).

The Spark SDK is imported lazily (inside ``__init__``) so importing
this module without ``pyspark`` installed raises an actionable error.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame
from pirn.nodes.source import Source


class SparkSource(Source):
    """Bind a Spark session + format/path or SQL query to emit a deferred frame."""

    def __init__(
        self,
        *,
        _config: KnotConfig,
        spark_session: Any,
        format: str = "parquet",
        path: str | None = None,
        query: str | None = None,
        options: Mapping[str, Any] | None = None,
        backend_name: str = "spark",
        source_uri: str = "",
        **kwargs: Any,
    ) -> None:
        try:
            import pyspark.sql  # noqa: F401  — verify availability
        except ImportError as exc:
            raise ImportError(
                "SparkSource requires pyspark; install with `pip install pirn[spark]`"
            ) from exc
        if spark_session is None:
            raise TypeError("SparkSource: spark_session is required")
        if path is None and query is None:
            raise TypeError(
                "SparkSource: either path=... or query=... must be supplied"
            )
        if path is not None and query is not None:
            raise TypeError(
                "SparkSource: path and query are mutually exclusive"
            )
        if path is not None:
            if not isinstance(path, str) or not path:
                raise ValueError("SparkSource: path must be a non-empty string")
            if not isinstance(format, str) or not format:
                raise ValueError("SparkSource: format must be a non-empty string")
        if query is not None:
            if not isinstance(query, str) or not query:
                raise ValueError("SparkSource: query must be a non-empty string")
        self._spark_session = spark_session
        self._format = format
        self._path = path
        self._query = query
        self._options: dict[str, Any] = dict(options or {})
        self._backend_name = backend_name
        self._source_uri = source_uri or (path or "")
        super().__init__(_config=_config, **kwargs)

    @property
    def path(self) -> str | None:
        return self._path

    @property
    def query(self) -> str | None:
        return self._query

    @property
    def backend_name(self) -> str:
        return self._backend_name

    async def process(self, **_: Any) -> SparkDataFrame:
        if self._query is not None:
            frame = self._spark_session.sql(self._query)
        else:
            assert self._path is not None
            reader = self._spark_session.read.format(self._format)
            if self._options:
                reader = reader.options(**self._options)
            frame = reader.load(self._path)
        return SparkDataFrame(
            frame=frame,
            backend_name=self._backend_name,
            source_uri=self._source_uri,
        )
