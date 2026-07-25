"""``LoadedDocument`` — the normalized document every loader emits (F25-S1).

A provider-neutral, frozen carrier for the text (and, for structured formats,
the records) extracted from one source object, plus source-derived metadata.
Every :class:`~pirn_agents.specializations.document_processing.loaders.loader.Loader`
returns one of these so downstream chunking, enrichment, and embedding depend
only on this shape, never on a concrete parser backend.

Multimodal (F15). Text loaders populate :attr:`text` (and :attr:`records` for
CSV/JSON) and leave :attr:`blocks` ``None``. Image/audio/binary loaders — e.g.
:class:`~pirn_agents.specializations.document_processing.loaders.media_loader.MediaLoader`
— emit the same :class:`LoadedDocument` shape with a typed
:attr:`blocks` sequence (and a text projection in :attr:`text` for
backward-compatible text-only consumers). The extension point is the ``Loader``
interface; :attr:`blocks` keeps the multimodal payload first-class rather than
smuggled through scalar :attr:`metadata`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.content_block import ContentBlock


@dataclass(frozen=True)
class LoadedDocument(PirnOpaqueValue):
    """One normalized document produced by a loader.

    Attributes
    ----------
    text:
        The extracted plain text; empty string for an empty source. For a
        multimodal document this is the text projection of :attr:`blocks`.
    metadata:
        Source-derived metadata (e.g. ``content_type``, ``page_count``,
        ``title``); scalar values only so it stays audit-friendly.
    source_id:
        Optional stable identifier of the source object (path, key, or URL).
    records:
        Structured rows for tabular/record formats (CSV, JSON arrays); ``None``
        for prose formats. Kept alongside :attr:`text` so a caller may chunk the
        prose or iterate the records.
    blocks:
        Typed multimodal content blocks (image/audio/file/text) for non-text
        sources; ``None`` for a plain text document (the backward-compatible
        default).
    """

    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    source_id: str | None = None
    records: tuple[Mapping[str, Any], ...] | None = None
    blocks: tuple[ContentBlock, ...] | None = None

    def __post_init__(self) -> None:
        """Validate that ``blocks`` (when set) is a sequence of content blocks.

        Raises:
            TypeError: If ``blocks`` is set but is not a tuple of
                :class:`~pirn_agents.types.content_block.ContentBlock`.
        """
        if self.blocks is None:
            return
        if not isinstance(self.blocks, tuple):
            raise TypeError("LoadedDocument: blocks must be a tuple of ContentBlock or None")
        for block in self.blocks:
            if not isinstance(block, ContentBlock):
                raise TypeError(
                    "LoadedDocument: every block must be a ContentBlock, "
                    f"got {type(block).__name__}"
                )
