"""Tests for :class:`StreamingFileFormat`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class TestStreamingFileFormat(unittest.TestCase):
    def test_streaming_is_true(self) -> None:
        fmt = StreamingFileFormat()
        self.assertTrue(fmt.streaming)
