"""Tests for :class:`Codec`."""

from __future__ import annotations

import unittest
from typing import AsyncIterator

from pirn.domains.connectors.file_formats.codec import Codec


async def _bytes_iter(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


class TestCodecInterface(unittest.IsolatedAsyncioTestCase):
    async def test_name_raises_not_implemented(self) -> None:
        codec = Codec()
        with self.assertRaises(NotImplementedError):
            _ = codec.name

    async def test_compress_stream_raises_not_implemented(self) -> None:
        codec = Codec()
        with self.assertRaises(NotImplementedError):
            await codec.compress_stream(_bytes_iter(b"data"))

    async def test_decompress_stream_raises_not_implemented(self) -> None:
        codec = Codec()
        with self.assertRaises(NotImplementedError):
            await codec.decompress_stream(_bytes_iter(b"data"))
