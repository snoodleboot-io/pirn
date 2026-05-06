"""``RecordWriter`` capability — write tabular records to a vendor.

Counterpart to :class:`TableSource`. Connectors that implement
:class:`RecordWriter` accept rows for upsert or insert into a vendor's
backing store (CRM, ticketing system, marketing automation).

Concrete implementations document upsert vs. insert semantics for their
vendor (Salesforce upsert by external id, HubSpot upsert by email,
Zendesk ticket create-only, ...).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class RecordWriter:
    """Capability for connectors that accept tabular writes."""

    async def write_records(
        self,
        records: Iterable[Mapping[str, Any]],
    ) -> int:
        """Persist ``records`` to the vendor; return the count written."""
        raise NotImplementedError(f"{type(self).__name__} must implement write_records()")
