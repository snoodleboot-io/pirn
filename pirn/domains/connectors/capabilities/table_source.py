"""``TableSource`` capability — paginated tabular reads from any vendor.

Connectors that implement :class:`TableSource` can be consumed by any
knot that accepts a ``TableSource`` parameter — the consumer doesn't
need to know whether the rows are coming from Stripe, Salesforce, GitHub
issues, or a Postgres table.

Pagination is uniform: callers pass a ``cursor`` (vendor-opaque token)
and receive ``(rows, next_cursor)``. ``next_cursor=None`` signals end of
stream. Concrete implementations encode whatever pagination shape their
vendor uses (offset, page-token, Link header, ``nextRecordsUrl``,
cursor) into the opaque string.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class TableSource:
    """Capability for connectors that emit paginated tabular records."""

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Fetch one page of records.

        Returns
        -------
        ``(rows, next_cursor)`` — a list of row dicts and the cursor to
        pass on the next call. ``next_cursor=None`` signals the stream
        is exhausted.

        Parameters
        ----------
        cursor:
            Opaque token returned by the previous ``fetch_page`` call,
            or ``None`` to start a new scan.
        page_size:
            Caller's preferred page size. Concrete implementations may
            clamp to vendor-specific limits.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_page()")
