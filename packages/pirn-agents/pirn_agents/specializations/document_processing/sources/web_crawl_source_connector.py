"""``WebCrawlSourceConnector`` — pull documents by crawling URLs (F25-S3 / PIR-613).

Built on the F16 :class:`~pirn.connectors.http_connector.HttpConnector`
(pooled, SSRF-guarded, retrying), it streams each seed URL's bytes, dedups by
content hash, and yields a
:class:`~pirn_agents.specializations.document_processing.sources.source_document.SourceDocument`.
A fetch failure on one URL (auth, network, rate limit, guard rejection) is
recorded on :attr:`errors` and skipped rather than aborting the crawl. ``httpx``
is lazily imported by the connector, so this module pulls no backend.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from pirn.connectors.http_connector import HttpConnector

from pirn_agents.specializations.document_processing.sources.content_hash_deduplicator import (
    ContentHashDeduplicator,
)
from pirn_agents.specializations.document_processing.sources.source_connector import (
    SourceConnector,
)
from pirn_agents.specializations.document_processing.sources.source_document import (
    SourceDocument,
)


class WebCrawlSourceConnector(SourceConnector):
    """Crawl a list of URLs via an :class:`HttpConnector`, deduped by hash."""

    def __init__(
        self,
        *,
        connector: HttpConnector,
        urls: Sequence[str],
        deduplicator: ContentHashDeduplicator | None = None,
    ) -> None:
        """Bind the connector to an HTTP client and a seed URL list.

        Args:
            connector: The F16 pooled, SSRF-guarded HTTP connector.
            urls: The seed URLs to fetch.
            deduplicator: Optional shared content-hash deduplicator; when
                ``None`` a fresh one is created.

        Raises:
            TypeError: If ``connector`` is not an :class:`HttpConnector`.
        """
        # PIR-722 reviewed this concrete-type guard and deliberately kept it.
        # HttpConnector is not merely "something with stream_bytes()": it is the
        # component that applies the egress/SSRF policy to every URL, pins the
        # request to the address that policy vetted (which is what closes DNS
        # rebinding), and keeps redirect-following off so the pin cannot be
        # sidestepped. This connector fetches caller-supplied seed URLs — the
        # canonical SSRF sink — so widening to a structural type would admit a
        # client that performs none of that vetting and make this class's
        # "pooled, SSRF-guarded" contract untrue. Depending on an abstraction
        # only helps once core has an HTTP interface that carries the egress
        # guarantee in its contract; that is core work, tracked as PIR-792.
        if not isinstance(connector, HttpConnector):
            raise TypeError(
                f"WebCrawlSourceConnector: connector must be an HttpConnector, "
                f"got {type(connector).__name__}"
            )
        self._connector = connector
        self._urls = tuple(urls)
        self._deduplicator = deduplicator if deduplicator is not None else ContentHashDeduplicator()
        self._errors: list[tuple[str, str]] = []

    async def fetch(self) -> AsyncIterator[SourceDocument]:
        """Yield each new URL's content as a :class:`SourceDocument`.

        Yields:
            One :class:`SourceDocument` per distinct-content URL; duplicates and
            failed fetches are skipped (the latter recorded on :attr:`errors`).
        """
        self._errors = []
        for url in self._urls:
            try:
                data = b"".join([chunk async for chunk in self._connector.stream_bytes("GET", url)])
            except Exception as exc:
                self._errors.append((url, str(exc)))
                continue
            if not self._deduplicator.is_new(data):
                continue
            yield SourceDocument.create(source_id=url, data=data, metadata={"source": "web_crawl"})

    @property
    def errors(self) -> tuple[tuple[str, str], ...]:
        """Return the ``(url, error)`` pairs skipped during the last fetch."""
        return tuple(self._errors)
