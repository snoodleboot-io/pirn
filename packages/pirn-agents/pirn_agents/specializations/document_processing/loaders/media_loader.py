"""``MediaLoader`` — load binary media (image/audio/file) into blocks (F15-S4).

The multimodal counterpart to the text loaders: it wraps the raw bytes of one
non-text source object into a :class:`LoadedDocument` carrying a single typed
content block (:class:`~pirn_agents.types.image_block.ImageBlock`,
:class:`~pirn_agents.types.audio_block.AudioBlock`, or
:class:`~pirn_agents.types.file_block.FileBlock`) rather than plain text — closing
the F15 multimodal seam the ``Loader`` interface documented. The block modality
is chosen from the IANA ``media_type`` prefix (``image/…`` → image, ``audio/…`` →
audio, anything else → file). Bytes ride inline on a
:class:`~pirn_agents.types.media_handle.MediaHandle`, so they never enter lineage;
any caption is mirrored into :attr:`LoadedDocument.text` so a text-only consumer
still degrades gracefully. Needs no optional backend — it only frames bytes.
"""

from __future__ import annotations

from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader
from pirn_agents.types.audio_block import AudioBlock
from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.file_block import FileBlock
from pirn_agents.types.image_block import ImageBlock
from pirn_agents.types.media_handle import MediaHandle


class MediaLoader(Loader):
    """Frame binary media bytes into a :class:`LoadedDocument` of content blocks."""

    def __init__(self, *, media_type: str, caption: str | None = None) -> None:
        """Configure the loader.

        Args:
            media_type: The IANA media (MIME) type of the source bytes, e.g.
                ``"image/png"`` or ``"audio/wav"``; its top-level type selects
                the emitted block modality.
            caption: Optional description/transcript/filename carried on the
                block as its text projection for graceful degradation.

        Raises:
            TypeError: If ``media_type`` is not a non-empty string, or
                ``caption`` is neither a string nor ``None``.
        """
        if not isinstance(media_type, str) or not media_type:
            raise TypeError("MediaLoader: media_type must be a non-empty str")
        if caption is not None and not isinstance(caption, str):
            raise TypeError(
                f"MediaLoader: caption must be a str or None, got {type(caption).__name__}"
            )
        self._media_type = media_type
        self._caption = caption

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        """Frame ``data`` into a multimodal :class:`LoadedDocument`.

        Args:
            data: The raw bytes of one media source object.
            source_id: Optional identifier recorded on the document.

        Returns:
            A :class:`LoadedDocument` whose :attr:`blocks` holds a single typed
            media block and whose :attr:`text` is that block's caption (or ``""``).

        Raises:
            TypeError: If ``data`` is not bytes.
        """
        raw = self._require_bytes("MediaLoader", data)
        handle = MediaHandle(media_type=self._media_type, data=raw)
        top_level = self._media_type.split("/", 1)[0]
        block: ContentBlock
        if top_level == "image":
            block = ImageBlock(source=handle, alt_text=self._caption)
        elif top_level == "audio":
            block = AudioBlock(source=handle, transcript=self._caption)
        else:
            block = FileBlock(source=handle, filename=self._caption)
        return LoadedDocument(
            text=block.as_text,
            metadata={"content_type": self._media_type},
            source_id=source_id,
            blocks=(block,),
        )
