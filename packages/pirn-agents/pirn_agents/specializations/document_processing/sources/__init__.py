"""Source connectors (F25-S3 / PIR-579).

Pull documents from object storage or a web crawl behind the shared
:class:`~pirn_agents.specializations.document_processing.sources.source_connector.SourceConnector`
interface, deduping by content hash so identical content is never re-ingested.
The connectors build on core's ``ObjectStore`` and the agents ``HttpConnector``; those
backends are lazily imported, so importing this package pulls no backend.
"""

from __future__ import annotations
