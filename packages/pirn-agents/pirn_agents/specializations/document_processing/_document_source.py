"""``_DocumentSource`` — the guarded connector source for document ingestion.

Replaces ``_DocumentLoader`` (deleted; PIR-868), which read files and HTTP(S)
URLs directly inside ``process()`` — the "ingestor anti-pattern" documented in
``docs/contributing/assembler-disassembler-pattern.md``. This is the Layer-2
connector-source half of the split: it owns the I/O and the SSRF /
path-traversal guards (delegated, unchanged, to :class:`_DocumentSourceReader`
— the one implementation every document-processing loader shares) and
produces raw ``bytes``. The bytes-in half, :class:`_DocumentAssembler`, does
the (guard-free) decode.

Algorithm:
    1. Delegate to :class:`_DocumentSourceReader` — the shared guarded
       reader — which validates ``source``, resolves the scheme, and
       either streams an SSRF-vetted HTTP(S) response or reads a
       path-traversal-guarded local file, decoding the result as text.
    2. Re-encode the decoded text as UTF-8 bytes so the connector boundary
       is byte-shaped, matching :class:`~pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`'s
       contract — the framework's own template for a Layer-2 connector
       Source. :class:`_DocumentAssembler` decodes it back on the other
       side, so the guarded reader's decoding logic (HTTP charset
       handling, ``errors="replace"``) is preserved unchanged; only the
       connector boundary's shape changes.

References:
    - docs/contributing/assembler-disassembler-pattern.md
    - :class:`pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`
      — the reference Layer-2 ``Source`` this mirrors.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source

from pirn_agents.specializations.document_processing._document_source_reader import (
    _DocumentSourceReader,
)


class _DocumentSource(Source):
    """Read a document ``source`` (local path or HTTP(S) URL) and return its bytes.

    All SSRF and path-traversal guarding is delegated unchanged to
    :class:`_DocumentSourceReader` — the single shared implementation every
    document-processing loader composes. This class adds nothing but the
    connector-boundary shape (``bytes`` out) that :class:`_DocumentAssembler`
    expects.
    """

    def __init__(
        self,
        *,
        source: Knot | str,
        _config: KnotConfig,
        allowed_root: Knot | str | None = None,
        allowed_hosts: Knot | tuple[str, ...] | None = None,
        max_bytes: Knot | int = _DocumentSourceReader.max_bytes,
        request_timeout: Knot | float = _DocumentSourceReader.request_timeout,
        connect_timeout: Knot | float = _DocumentSourceReader.connect_timeout,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source=source,
            allowed_root=allowed_root,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            request_timeout=request_timeout,
            connect_timeout=connect_timeout,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source: str,
        allowed_root: str | None = None,
        allowed_hosts: tuple[str, ...] | None = None,
        max_bytes: int = _DocumentSourceReader.max_bytes,
        request_timeout: float = _DocumentSourceReader.request_timeout,
        connect_timeout: float = _DocumentSourceReader.connect_timeout,
        **_: Any,
    ) -> bytes:
        """Read ``source`` under the shared security policy and return its bytes.

        Args:
            source: A local file path, a ``file://`` URI, or an ``http(s)://`` URL.
            allowed_root: Directory local reads must resolve within. ``None``
                rejects local reads outright.
            allowed_hosts: Optional hostname allow-list for URL fetches.
            max_bytes: Maximum source size in bytes.
            request_timeout: HTTP request timeout in seconds.
            connect_timeout: HTTP connection timeout in seconds.

        Returns:
            The source's content, UTF-8 encoded.

        Raises:
            TypeError: If source is not a non-empty string.
            ValueError: If the scheme is unsupported, the path resolves outside
                ``allowed_root``, the file exceeds ``max_bytes``, or the host is
                unresolvable, private/loopback/link-local, or not allow-listed.
        """
        reader = _DocumentSourceReader(
            allowed_root=allowed_root,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            request_timeout=request_timeout,
            connect_timeout=connect_timeout,
        )
        text = await reader.read(source)
        return text.encode("utf-8")
