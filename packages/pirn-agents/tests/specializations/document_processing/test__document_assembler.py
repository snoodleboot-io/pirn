"""Unit tests for :class:`_DocumentAssembler`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._document_assembler import (
    _DocumentAssembler,
)


def _make_knot() -> _DocumentAssembler:
    with Tapestry():
        return _DocumentAssembler(body=b"placeholder", _config=KnotConfig(id="asm"))


class TestDocumentAssembler(unittest.IsolatedAsyncioTestCase):
    async def test_decodes_utf8_bytes(self) -> None:
        knot = _make_knot()
        result = await knot.process(body=b"hello world")
        assert result == "hello world"

    async def test_replaces_invalid_utf8_bytes(self) -> None:
        knot = _make_knot()
        result = await knot.process(body=b"\xff\xfehello")
        assert "hello" in result

    async def test_rejects_non_bytes(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "must be bytes"):
            await knot.process(body="not bytes")  # type: ignore[arg-type]
