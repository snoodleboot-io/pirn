"""``EventEmitter`` capability — outbound event ingestion to a vendor.

Connectors that implement :class:`EventEmitter` accept event payloads
(analytics, audit, telemetry) and forward them to the vendor's
ingestion API. Used for ingestion-style SaaS APIs like Mixpanel,
Amplitude, custom Datadog metrics.

For batch ingestion, callers loop over :meth:`emit` or use
:meth:`emit_many` if the vendor supports a bulk endpoint.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


class EventEmitter:
    """Capability for connectors that ingest event payloads."""

    async def emit(self, event: Mapping[str, Any]) -> None:
        """Send a single event to the vendor's ingestion endpoint.

        Concrete implementations document the required keys in
        ``event`` for their vendor (e.g., Mixpanel needs
        ``{"distinct_id", "event", "properties"}``).
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement emit()"
        )

    async def emit_many(self, events: Iterable[Mapping[str, Any]]) -> int:
        """Send a batch of events; return the count successfully accepted.

        The default implementation calls :meth:`emit` per event.
        Vendors with bulk endpoints should override.
        """
        count = 0
        for event in events:
            await self.emit(event)
            count += 1
        return count
