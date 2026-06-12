"""``SparkSource`` — pirn :class:`Source` that emits a deferred
:class:`SparkDataFrame`.

Two construction modes:

1. ``path`` (+ optional ``format`` / ``options``) — the source calls
   ``session.read.format(format).options(**options).load(path)``.
2. ``query`` — the source calls ``session.sql(query)`` to produce a
   deferred frame from a SQL statement (catalog tables / temp views).

The Spark SDK import is verified inside ``process()`` so importing
this module without ``pyspark`` installed raises an actionable error
at execution time.

Algorithm:
    1. Receive resolved ``spark_session``, ``format``, ``path``, ``query``,
       ``options``, ``backend_name``, and ``source_uri`` values in ``process()``.
    2. Validate that ``pyspark`` is importable; raise ``ImportError`` with
       install instructions if not.
    3. Validate that ``spark_session`` is not ``None``.
    4. Validate mutual exclusion: exactly one of ``path`` or ``query`` must
       be supplied.
    5. Validate that ``path`` and ``format`` are non-empty strings when in
       path mode; validate that ``query`` is a non-empty string when in query
       mode.
    6. If ``query`` mode: call ``spark_session.sql(query)`` to build the
       deferred logical plan.
    7. If ``path`` mode: chain
       ``spark_session.read.format(format).options(**options).load(path)``
       to build the deferred logical plan.
    8. Wrap the resulting Spark DataFrame in a :class:`SparkDataFrame` and
       return it.

References:
    [1] PySpark DataFrameReader API:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/io.html
    [2] PySpark SparkSession.sql:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.SparkSession.sql.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame
from pirn.nodes.source import Source


class SparkSource(Source):
    """Bind a Spark session + format/path or SQL query to emit a deferred frame."""

    def __init__(
        self,
        *,
        _config: KnotConfig,
        spark_session: Knot | Any,
        format: Knot | str = "parquet",
        path: Knot | str | None = None,
        query: Knot | str | None = None,
        options: Knot | Mapping[str, Any] | None = None,
        backend_name: Knot | str = "spark",
        source_uri: Knot | str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            spark_session=spark_session,
            format=format,
            path=path,
            query=query,
            options=options,
            backend_name=backend_name,
            source_uri=source_uri,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        spark_session: Any,
        format: str = "parquet",
        path: str | None = None,
        query: str | None = None,
        options: Mapping[str, Any] | None = None,
        backend_name: str = "spark",
        source_uri: str = "",
        **_: Any,
    ) -> SparkDataFrame:
        """Load data from the configured path or SQL query into a deferred SparkDataFrame.

        Returns:
            A SparkDataFrame wrapping the newly created deferred Spark logical plan.
        """
        try:
            import pyspark.sql  # noqa: F401  — verify availability
        except ImportError as exc:
            raise ImportError(
                "SparkSource requires pyspark; install with `pip install pirn[spark]`"
            ) from exc

        if spark_session is None:
            raise TypeError("SparkSource: spark_session is required")
        if path is None and query is None:
            raise TypeError("SparkSource: either path=... or query=... must be supplied")
        if path is not None and query is not None:
            raise TypeError("SparkSource: path and query are mutually exclusive")
        if path is not None:
            if not isinstance(path, str) or not path:
                raise ValueError("SparkSource: path must be a non-empty string")
            if not isinstance(format, str) or not format:
                raise ValueError("SparkSource: format must be a non-empty string")
        if query is not None:
            if not isinstance(query, str) or not query:
                raise ValueError("SparkSource: query must be a non-empty string")

        resolved_options: dict[str, Any] = dict(options or {})
        resolved_uri = source_uri or (path or "")

        if query is not None:
            frame = spark_session.sql(query)
        else:
            assert path is not None
            reader = spark_session.read.format(format)
            if resolved_options:
                reader = reader.options(**resolved_options)
            frame = reader.load(path)

        return SparkDataFrame(
            frame=frame,
            backend_name=backend_name,
            source_uri=resolved_uri,
        )
