"""``Loader`` — the provider-neutral document-loader interface (F25-S1 / PIR-571).

Every concrete loader (PDF, HTML, Markdown, docx, code, CSV, JSON) implements
this one contract: given the raw bytes of a source object, return a normalized
:class:`~pirn_agents.specializations.document_processing.loaders.loaded_document.LoadedDocument`.
Loaders take bytes (not a path) so they compose directly with the streaming
source connectors (F25-S3) and stay trivially testable with in-memory fixtures —
no real files or services.

Multimodal seam (F15, deferred). This interface is the extension point for the
deferred F15 (Phase 5, not merged) multimodal loaders: an image/audio/PDF-image
loader is simply another ``Loader`` implementation emitting a
:class:`LoadedDocument`. Only the text loaders are implemented here; multimodal
ones are intentionally out of scope until F15 merges.
"""

from __future__ import annotations

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)


class Loader(PirnOpaqueValue):
    """Interface every document loader satisfies: bytes → :class:`LoadedDocument`."""

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        """Parse ``data`` into a normalized document.

        Args:
            data: The raw bytes of one source object.
            source_id: Optional stable identifier (path, key, or URL) recorded
                on the returned document.

        Returns:
            The normalized :class:`LoadedDocument`.

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement load()")

    @staticmethod
    def _require_bytes(loader_name: str, data: bytes) -> bytes:
        """Return ``data`` as ``bytes``, raising a clear ``TypeError`` otherwise.

        Shared front-door validation so every loader rejects a non-bytes source
        with the same actionable message rather than a deep backend traceback.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"{loader_name}: data must be bytes, got {type(data).__name__}")
        return bytes(data)
