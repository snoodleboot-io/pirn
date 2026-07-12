"""``LoadedDocument`` — the normalized document every loader emits (F25-S1).

A provider-neutral, frozen carrier for the text (and, for structured formats,
the records) extracted from one source object, plus source-derived metadata.
Every :class:`~pirn_agents.specializations.document_processing.loaders.loader.Loader`
returns one of these so downstream chunking, enrichment, and embedding depend
only on this shape, never on a concrete parser backend.

Multimodal seam (F15, deferred). Text loaders populate :attr:`text` (and
:attr:`records` for CSV/JSON). Image/audio/multimodal loaders are deferred to
F15 (Phase 5, not merged); when they land they emit the same
:class:`LoadedDocument` shape, carrying their block payloads under
:attr:`metadata` (e.g. an ``F15 blocks`` key) so this contract does not change.
The extension point is the ``Loader`` interface, not this dataclass.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class LoadedDocument(PirnOpaqueValue):
    """One normalized document produced by a loader.

    Attributes
    ----------
    text:
        The extracted plain text; empty string for an empty source.
    metadata:
        Source-derived metadata (e.g. ``content_type``, ``page_count``,
        ``title``); scalar values only so it stays audit-friendly.
    source_id:
        Optional stable identifier of the source object (path, key, or URL).
    records:
        Structured rows for tabular/record formats (CSV, JSON arrays); ``None``
        for prose formats. Kept alongside :attr:`text` so a caller may chunk the
        prose or iterate the records.
    """

    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    source_id: str | None = None
    records: tuple[Mapping[str, Any], ...] | None = None
