"""``StreamingFileFormat`` — incremental decode/encode marker base.

Subclasses implement :meth:`read` and :meth:`write` directly; the
``streaming`` property returns ``True``.
"""

from __future__ import annotations

from pirn.connectors.file_format import FileFormat


class StreamingFileFormat(FileFormat):
    """Marker base for formats that decode/encode incrementally.

    Subclasses must implement :meth:`name`, :meth:`read`, :meth:`write`.
    They do **not** need to override :attr:`streaming` — it is set to
    ``True`` here.
    """

    @property
    def streaming(self) -> bool:
        return True
