"""``SourceDocument`` — one fetched source object with its content hash (F25-S3).

The neutral unit a source connector yields: the raw bytes of one object plus a
content-address (SHA-256 hex) used for dedup and, downstream, incremental
upsert-by-hash (F25-S4). Frozen and opaque so it travels the pirn graph without
being hashed by value.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SourceDocument(PirnOpaqueValue):
    """One fetched object: its id, bytes, content hash, and metadata.

    Attributes
    ----------
    source_id:
        Stable identifier of the object (object-store key or crawl URL).
    data:
        The raw fetched bytes, ready to hand to a loader.
    content_hash:
        SHA-256 hex digest of :attr:`data`; the content address for dedup.
    metadata:
        Connector-supplied scalar metadata (e.g. ``source`` origin label).
    """

    source_id: str
    data: bytes
    content_hash: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        data: bytes,
        metadata: Mapping[str, Any] | None = None,
    ) -> SourceDocument:
        """Build a document, computing the SHA-256 content hash from ``data``.

        Args:
            source_id: Stable identifier of the object.
            data: The raw fetched bytes.
            metadata: Optional metadata mapping; defaults to empty.

        Returns:
            A frozen :class:`SourceDocument` with its ``content_hash`` filled in.
        """
        return cls(
            source_id=source_id,
            data=bytes(data),
            content_hash=hashlib.sha256(bytes(data)).hexdigest(),
            metadata=dict(metadata) if metadata is not None else {},
        )
