"""``ArchiveFileFormat`` — multi-file archive wrapper (tar, zip).

Where :class:`CompressedFileFormat` wraps a single file with a codec,
:class:`ArchiveFileFormat` wraps a *bundle of files* — each entry is
decoded by the inner :class:`FileFormat`. Records are emitted as
``{"_archive_member": str, **record}`` so callers can identify the
source file.

Supported archive types: ``"tar"``, ``"tar.gz"``, ``"tar.bz2"``,
``"tar.zst"``, ``"zip"``. ``"tar.zst"`` requires ``zstandard``.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from typing import Any, AsyncIterator, ClassVar, Mapping

from pirn.domains.connectors.file_format import FileFormat


class ArchiveFileFormat(FileFormat):
    """Wrap a :class:`FileFormat` for tar/zip multi-file archives.

    Each member file is decoded by *inner* and its records are tagged
    with ``{"_archive_member": "<member path>", ...original fields...}``.

    On write, each record must carry ``_archive_member`` (the member
    path inside the archive); records with the same member name are
    grouped and encoded together via *inner*.

    Args:
        inner: The :class:`FileFormat` applied to each archive member.
        archive_type: One of ``"tar"``, ``"tar.gz"``, ``"tar.bz2"``,
            ``"tar.zst"``, ``"zip"``.
    """

    _supported_archives: ClassVar[frozenset[str]] = frozenset(
        {"tar", "tar.gz", "tar.bz2", "tar.zst", "zip"}
    )

    _tar_modes: ClassVar[dict[str, str]] = {
        "tar": "r:",
        "tar.gz": "r:gz",
        "tar.bz2": "r:bz2",
        "tar.zst": "r:*",
    }

    _tar_write_modes: ClassVar[dict[str, str]] = {
        "tar": "w:",
        "tar.gz": "w:gz",
        "tar.bz2": "w:bz2",
        "tar.zst": "w:",
    }

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
        payload = await self._drain_bytes(body)
        archive_type = self._archive_type
        inner = self._inner

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            if archive_type == "zip":
                async for record in ArchiveFileFormat._read_zip(
                    inner, payload
                ):
                    yield record
            else:
                async for record in ArchiveFileFormat._read_tar(
                    inner, payload, archive_type
                ):
                    yield record

        return _iter()

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        materialised = await self._drain_records(records)
        archive_type = self._archive_type
        inner = self._inner

        grouped = ArchiveFileFormat._group_by_member(materialised)

        if archive_type == "zip":
            payload = await ArchiveFileFormat._write_zip(inner, grouped)
        else:
            payload = await ArchiveFileFormat._write_tar(
                inner, grouped, archive_type
            )

        async def _iter() -> AsyncIterator[bytes]:
            yield payload

        return _iter()

    @staticmethod
    def _validate_member_path(name: str) -> None:
        """Raise ValueError if *name* is unsafe to use as an archive member path."""
        if not name:
            raise ValueError(
                "ArchiveFileFormat: archive member path must be non-empty"
            )
        if "\x00" in name:
            raise ValueError(
                f"ArchiveFileFormat: archive member path contains NUL byte: {name!r}"
            )
        import os.path as _osp
        if _osp.isabs(name):
            raise ValueError(
                f"ArchiveFileFormat: archive member path must be relative, got {name!r}"
            )
        parts = name.replace("\\", "/").split("/")
        if ".." in parts:
            raise ValueError(
                f"ArchiveFileFormat: archive member path contains '..' component: {name!r}"
            )

    @staticmethod
    def _group_by_member(
        records: list[Mapping[str, Any]],
    ) -> dict[str, list[Mapping[str, Any]]]:
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for record in records:
            member = record.get("_archive_member")
            if not isinstance(member, str) or not member:
                raise ValueError(
                    "ArchiveFileFormat: every record must have a non-empty "
                    "'_archive_member' string field"
                )
            ArchiveFileFormat._validate_member_path(member)
            inner_record = {
                k: v for k, v in record.items() if k != "_archive_member"
            }
            grouped.setdefault(member, []).append(inner_record)
        return grouped

    @staticmethod
    async def _read_zip(
        inner: FileFormat, payload: bytes
    ) -> AsyncIterator[Mapping[str, Any]]:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                member_bytes = zf.read(info.filename)
                member_name = info.filename

                async def _byte_iter(
                    data: bytes = member_bytes,
                ) -> AsyncIterator[bytes]:
                    yield data

                ArchiveFileFormat._validate_member_path(member_name)
                async for record in await inner.read(_byte_iter()):
                    yield {"_archive_member": member_name, **record}

    @staticmethod
    async def _read_tar(
        inner: FileFormat, payload: bytes, archive_type: str
    ) -> AsyncIterator[Mapping[str, Any]]:
        if archive_type == "tar.zst":
            try:
                import zstandard as zstd
            except ImportError as exc:
                raise ImportError(
                    "ArchiveFileFormat: tar.zst requires zstandard. "
                    "Install with `pip install pirn[zstd]`."
                ) from exc
            dctx = zstd.ZstdDecompressor()
            raw = dctx.decompress(payload)
            tf = tarfile.open(fileobj=io.BytesIO(raw), mode="r:")
        else:
            mode = ArchiveFileFormat._tar_modes.get(archive_type, "r:*")
            tf = tarfile.open(fileobj=io.BytesIO(payload), mode=mode)

        try:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                fobj = tf.extractfile(member)
                if fobj is None:
                    continue
                member_bytes = fobj.read()
                member_name = member.name

                async def _byte_iter(
                    data: bytes = member_bytes,
                ) -> AsyncIterator[bytes]:
                    yield data

                ArchiveFileFormat._validate_member_path(member_name)
                async for record in await inner.read(_byte_iter()):
                    yield {"_archive_member": member_name, **record}
        finally:
            tf.close()

    @staticmethod
    async def _write_zip(
        inner: FileFormat,
        grouped: dict[str, list[Mapping[str, Any]]],
    ) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for member_name, member_records in grouped.items():

                async def _record_iter(
                    recs: list[Mapping[str, Any]] = member_records,
                ) -> AsyncIterator[Mapping[str, Any]]:
                    for r in recs:
                        yield r

                chunks: list[bytes] = []
                async for chunk in await inner.write(_record_iter()):
                    chunks.append(chunk)
                zf.writestr(member_name, b"".join(chunks))
        return buf.getvalue()

    @staticmethod
    async def _write_tar(
        inner: FileFormat,
        grouped: dict[str, list[Mapping[str, Any]]],
        archive_type: str,
    ) -> bytes:
        buf = io.BytesIO()
        if archive_type == "tar.zst":
            raw_buf = io.BytesIO()
            tf = tarfile.open(fileobj=raw_buf, mode="w:")
        else:
            mode = ArchiveFileFormat._tar_write_modes.get(archive_type, "w:")
            tf = tarfile.open(fileobj=buf, mode=mode)

        try:
            for member_name, member_records in grouped.items():

                async def _record_iter(
                    recs: list[Mapping[str, Any]] = member_records,
                ) -> AsyncIterator[Mapping[str, Any]]:
                    for r in recs:
                        yield r

                chunks: list[bytes] = []
                async for chunk in await inner.write(_record_iter()):
                    chunks.append(chunk)
                data = b"".join(chunks)
                info = tarfile.TarInfo(name=member_name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        finally:
            tf.close()

        if archive_type == "tar.zst":
            try:
                import zstandard as zstd
            except ImportError as exc:
                raise ImportError(
                    "ArchiveFileFormat: tar.zst requires zstandard. "
                    "Install with `pip install pirn[zstd]`."
                ) from exc
            cctx = zstd.ZstdCompressor()
            return cctx.compress(raw_buf.getvalue())

        return buf.getvalue()
