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

from pirn.connectors.file_format import FileFormat
from pirn.connectors.file_formats.codec import Codec
from pirn.connectors.file_formats.codecs.bzip2_codec import Bzip2Codec
from pirn.connectors.file_formats.codecs.gzip_codec import GzipCodec
from pirn.connectors.file_formats.codecs.lz4_codec import Lz4Codec
from pirn.connectors.file_formats.codecs.snappy_codec import SnappyCodec
from pirn.connectors.file_formats.codecs.zstd_codec import ZstdCodec


class CompressedFileFormat(FileFormat):
    """Wrap a :class:`FileFormat` with a transparent codec.

    Supported codecs: ``"gzip"``, ``"bzip2"``, ``"zstd"``, ``"snappy"``,
    ``"lz4"``.
    """

    #: The supported codecs and what builds each one. Single source of truth:
    #: the constructor validates against these keys and :meth:`_load_codec`
    #: reads the value, so a new codec cannot be accepted by one and unknown to
    #: the other.
    _codec_types: ClassVar[Mapping[str, type[Codec]]] = {
        "gzip": GzipCodec,
        "bzip2": Bzip2Codec,
        "zstd": ZstdCodec,
        "snappy": SnappyCodec,
        "lz4": Lz4Codec,
    }

    def __init__(self, inner: FileFormat, *, codec: str) -> None:
        if not isinstance(inner, FileFormat):
            raise TypeError("CompressedFileFormat: inner must be a FileFormat")
        if codec not in self._codec_types:
            raise ValueError(
                f"CompressedFileFormat: codec must be one of "
                f"{sorted(self._codec_types)}, got {codec!r}"
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

    def _load_codec(self) -> Codec:
        """Build the codec; its optional backend is imported when it runs."""
        return self._codec_types[self._codec]()
