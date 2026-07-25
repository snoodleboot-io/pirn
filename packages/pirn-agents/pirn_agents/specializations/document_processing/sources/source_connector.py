"""``SourceConnector`` — the source-ingestion interface (F25-S3 / PIR-579).

Every source (object storage, web crawl, and future Drive-style sources) yields
:class:`~pirn_agents.specializations.document_processing.sources.source_document.SourceDocument`
objects through this one contract, so the ingestion pipeline (F25-S5) depends
only on the interface, never a concrete backend. Implementations must isolate
per-object failures (auth, network, rate limit) so one bad object never aborts
the stream — surfaced via :attr:`errors`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.document_processing.sources.source_document import (
    SourceDocument,
)


class SourceConnector(PirnOpaqueValue):
    """Interface every source connector satisfies: yield :class:`SourceDocument`s."""

    def fetch(self) -> AsyncIterator[SourceDocument]:
        """Yield each source object as a :class:`SourceDocument`.

        Per-object failures must be isolated (recorded on :attr:`errors`), not
        raised, so ingestion never crashes on one unreadable object.

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement fetch()")

    @property
    def errors(self) -> tuple[tuple[str, str], ...]:
        """Return the ``(source_id, error)`` pairs skipped during the last fetch."""
        return ()
