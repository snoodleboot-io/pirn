"""``CompressedFileFormat`` — transparent codec wrapper around any
:class:`FileFormat`.

Composes naturally:

    parquet_zst = CompressedFileFormat(ParquetFormat(), codec="zstd")
    csv_gz = CompressedFileFormat(CsvFormat(...), codec="gzip")

Streaming codecs (gzip, zstd, lz4) preserve the inner format's
``streaming`` flag. Batch-only codecs would force ``streaming=False``;
none of the supported five (gzip, bzip2, zstd, snappy, lz4) do this.

Codec implementations live under ``codecs/`` and provide
:meth:`compress_stream` / :meth:`decompress_stream` helpers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any, ClassVar

from pirn.domains.connectors.file_format import FileFormat


class CompressedFileFormat(FileFormat):
    """Wrap a :class:`FileFormat` with a transparent codec.

    Supported codecs: ``"gzip"``, ``"bzip2"``, ``"zstd"``, ``"snappy"``,
    ``"lz4"``.
    """

    _supported_codecs: ClassVar[frozenset[str]] = frozenset(
        {"gzip", "bzip2", "zstd", "snappy", "lz4"}
    )

    def __init__(self, inner: FileFormat, *, codec: str) -> None:
        if not isinstance(inner, FileFormat):
            raise TypeError("CompressedFileFormat: inner must be a FileFormat")
        if codec not in self._supported_codecs:
            raise ValueError(
                f"CompressedFileFormat: codec must be one of "
                f"{sorted(self._supported_codecs)}, got {codec!r}"
            )
        self._inner = inner
        self._codec = codec

    @property
    def name(self) -> str:
        return f"{self._inner.name}+{self._codec}"

    @property
    def streaming(self) -> bool:
        return self._inner.streaming

    @property
    def inner(self) -> FileFormat:
        return self._inner

    @property
    def codec(self) -> str:
        return self._codec

    async def read(self, body: AsyncIterator[bytes]) -> AsyncIterator[Mapping[str, Any]]:
        decompressed = self._decompress_stream(body)
        return await self._inner.read(decompressed)

    async def write(self, records: AsyncIterator[Mapping[str, Any]]) -> AsyncIterator[bytes]:
        encoded = await self._inner.write(records)
        return self._compress_stream(encoded)

    async def _compress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        codec = self._load_codec()
        async for chunk in codec.compress_stream(body):
            yield chunk

    async def _decompress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        codec = self._load_codec()
        async for chunk in codec.decompress_stream(body):
            yield chunk

    def _load_codec(self) -> Any:
        """Lazy-import the codec module; raises on missing extra."""
        if self._codec == "gzip":
            from pirn.domains.connectors.file_formats.codecs.gzip_codec import (
                GzipCodec,
            )

            return GzipCodec()
        if self._codec == "bzip2":
            from pirn.domains.connectors.file_formats.codecs.bzip2_codec import (
                Bzip2Codec,
            )

            return Bzip2Codec()
        if self._codec == "zstd":
            from pirn.domains.connectors.file_formats.codecs.zstd_codec import (
                ZstdCodec,
            )

            return ZstdCodec()
        if self._codec == "snappy":
            from pirn.domains.connectors.file_formats.codecs.snappy_codec import (
                SnappyCodec,
            )

            return SnappyCodec()
        if self._codec == "lz4":
            from pirn.domains.connectors.file_formats.codecs.lz4_codec import (
                Lz4Codec,
            )

            return Lz4Codec()
        raise RuntimeError(f"CompressedFileFormat: codec {self._codec!r} not loadable")
