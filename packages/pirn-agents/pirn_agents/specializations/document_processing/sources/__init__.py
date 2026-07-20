"""Source connectors (F25-S3 / PIR-579).

Pull documents from object storage or a web crawl behind the shared
:class:`~pirn_agents.specializations.document_processing.sources.source_connector.SourceConnector`
interface, deduping by content hash so identical content is never re-ingested.
The connectors build on core's ``ObjectStore`` and the agents ``HttpConnector``; those
backends are lazily imported, so importing this package pulls no backend.
"""

from __future__ import annotations

from pirn_agents.specializations.document_processing.sources.content_hash_deduplicator import (
    ContentHashDeduplicator,
)
from pirn_agents.specializations.document_processing.sources.object_store_source_connector import (
    ObjectStoreSourceConnector,
)
from pirn_agents.specializations.document_processing.sources.source_connector import (
    SourceConnector,
)
from pirn_agents.specializations.document_processing.sources.source_document import (
    SourceDocument,
)
from pirn_agents.specializations.document_processing.sources.web_crawl_source_connector import (
    WebCrawlSourceConnector,
)

__all__: list[str] = [
    "ContentHashDeduplicator",
    "ObjectStoreSourceConnector",
    "SourceConnector",
    "SourceDocument",
    "WebCrawlSourceConnector",
]
