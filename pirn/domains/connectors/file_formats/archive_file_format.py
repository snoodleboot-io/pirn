"""``ArchiveFileFormat`` — multi-file archive wrapper (tar, zip).

Where :class:`CompressedFileFormat` wraps a single file with a codec,
:class:`ArchiveFileFormat` wraps a *bundle of files* — each entry is
decoded by the inner :class:`FileFormat`. Records are emitted as
``{"_archive_member": str, **record}`` so callers can identify the
source file.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, ClassVar, Mapping

from pirn.domains.connectors.file_format import FileFormat


class ArchiveFileFormat(FileFormat):
    """Wrap a :class:`FileFormat` for tar/zip multi-file archives.

    Supported archive types: ``"tar"``, ``"tar.gz"``, ``"tar.bz2"``,
    ``"tar.zst"``, ``"zip"``.
    """

    _supported_archives: ClassVar[frozenset[str]] = frozenset(
        {"tar", "tar.gz", "tar.bz2", "tar.zst", "zip"}
    )

    def __init__(
        self, inner: FileFormat, *, archive_type: str
    ) -> None:
        if not isinstance(inner, FileFormat):
            raise TypeError(
                "ArchiveFileFormat: inner must be a FileFormat"
            )
        if archive_type not in self._supported_archives:
            raise ValueError(
                f"ArchiveFileFormat: archive_type must be one of "
                f"{sorted(self._supported_archives)}, got {archive_type!r}"
            )
        self._inner = inner
        self._archive_type = archive_type

    @property
    def name(self) -> str:
        return f"{self._archive_type}({self._inner.name})"

    @property
    def streaming(self) -> bool:
        # Archive walking requires random access to entries; treat as batch.
        return False

    @property
    def inner(self) -> FileFormat:
        return self._inner

    @property
    def archive_type(self) -> str:
        return self._archive_type

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Stub — Wave A4 implementation lands the tar/zip walker."""
        raise NotImplementedError(
            "ArchiveFileFormat.read() is implemented in Wave A4 "
            "(compression + archive support)"
        )

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError(
            "ArchiveFileFormat.write() is implemented in Wave A4"
        )
