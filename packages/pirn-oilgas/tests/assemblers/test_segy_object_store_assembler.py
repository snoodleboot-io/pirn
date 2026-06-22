"""Unit tests for :class:`SegyObjectStoreAssembler`."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_oilgas.assemblers.segy_object_store_assembler import SegyObjectStoreAssembler
from pirn_oilgas.types.segy_volume import SegyVolume


def _body_param() -> Parameter:
    return Parameter("body", bytes, _config=KnotConfig(id="body"))


def _make(volume_id: str = "vol-01") -> SegyObjectStoreAssembler:
    return SegyObjectStoreAssembler(
        body=_body_param(),
        volume_id=volume_id,
        _config=KnotConfig(id="assembler"),
    )


def _fake_decode(body: bytes, volume_id: str) -> SegyVolume:
    return SegyVolume(volume_id=volume_id, inline_count=10, xline_count=20, sample_count=500)


class TestSegyObjectStoreAssembler(unittest.IsolatedAsyncioTestCase):

    async def test_returns_segy_volume(self) -> None:
        knot = _make("vol-01")
        with patch(
            "pirn_oilgas.assemblers.segy_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(body=b"segy-bytes", volume_id="vol-01")
        assert isinstance(result, SegyVolume)

    async def test_metadata_volume_id_matches(self) -> None:
        knot = _make("vol-01")
        with patch(
            "pirn_oilgas.assemblers.segy_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(body=b"segy-bytes", volume_id="vol-01")
        assert result.volume_id == "vol-01"

    async def test_metadata_inline_count_populated(self) -> None:
        knot = _make("vol-01")
        with patch(
            "pirn_oilgas.assemblers.segy_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(body=b"segy-bytes", volume_id="vol-01")
        assert result.inline_count == 10

    async def test_rejects_non_bytes_body(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="body must be bytes"):
            await knot.process(body="not-bytes", volume_id="vol-01")  # type: ignore[arg-type]

    async def test_rejects_non_str_volume_id(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="volume_id must be str"):
            await knot.process(body=b"x", volume_id=99)  # type: ignore[arg-type]

    async def test_rejects_empty_volume_id(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="volume_id must be non-empty"):
            await knot.process(body=b"x", volume_id="")
