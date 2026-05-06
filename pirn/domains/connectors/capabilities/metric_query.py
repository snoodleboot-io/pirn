"""``MetricQuery`` capability — issue PromQL/MetricsQL/equivalent queries.

For observability connectors that expose a query API (Prometheus,
Datadog query, Grafana datasource queries). The query string is vendor-
specific; the response shape is normalised to a mapping the caller can
inspect for series + datapoints.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any


class MetricQuery:
    """Capability for connectors that answer metric queries."""

    async def query(
        self,
        query: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str | None = None,
    ) -> Mapping[str, Any]:
        """Run ``query`` over the optional ``[start, end]`` window.

        Returns the vendor's parsed response. ``start`` / ``end`` /
        ``step`` are passed when supplied; concrete implementations
        clamp or ignore them per their API.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement query()")
