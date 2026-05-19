"""Unit tests for :class:`LasObjectStoreAssembler`."""

from __future__ import annotations

import unittest

try:
    import lasio  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lasio not installed") from _e

from unittest.mock import patch

import numpy as np
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.oilgas.assemblers.las_object_store_assembler import LasObjectStoreAssembler
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.types.las_payload import LASPayload


def _body_param() -> Parameter:
    return Parameter("body", bytes, _config=KnotConfig(id="body"))


def _make(well_id: str = "W-01") -> LasObjectStoreAssembler:
    return LasObjectStoreAssembler(
        body=_body_param(),
        well_id=well_id,
        curves=("GR", "RHOB"),
        depth_unit="m",
        _config=KnotConfig(id="assembler"),
    )


def _fake_decode(
    body: bytes,
    well_id: str,
    curves: tuple[str, ...],
    depth_unit: str,
) -> LASPayload:
    return LASPayload(
        metadata=LASFile(well_id=well_id, curves=curves, depth_unit=depth_unit),
        data={c: np.zeros(100, dtype=np.float64) for c in curves},
    )


class TestLasObjectStoreAssembler(unittest.IsolatedAsyncioTestCase):

    async def test_returns_las_payload(self) -> None:
        knot = _make("W-01")
        with patch(
            "pirn.domains.oilgas.assemblers.las_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(body=b"las-bytes", well_id="W-01", curves=("GR", "RHOB"), depth_unit="m")
        assert isinstance(result, LASPayload)

    async def test_metadata_well_id_matches(self) -> None:
        knot = _make("W-01")
        with patch(
            "pirn.domains.oilgas.assemblers.las_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(body=b"las-bytes", well_id="W-01", curves=("GR", "RHOB"), depth_unit="m")
        assert result.las.well_id == "W-01"

    async def test_metadata_curves_populated(self) -> None:
        knot = _make("W-01")
        with patch(
            "pirn.domains.oilgas.assemblers.las_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(body=b"las-bytes", well_id="W-01", curves=("GR", "RHOB"), depth_unit="m")
        assert result.las.curves == ("GR", "RHOB")

    async def test_rejects_non_bytes_body(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="body must be bytes"):
            await knot.process(body="not-bytes", well_id="W-01", curves=("GR",), depth_unit="m")  # type: ignore[arg-type]

    async def test_rejects_non_str_well_id(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="well_id must be str"):
            await knot.process(body=b"x", well_id=42, curves=("GR",), depth_unit="m")  # type: ignore[arg-type]

    async def test_rejects_empty_well_id(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="well_id must be non-empty"):
            await knot.process(body=b"x", well_id="", curves=("GR",), depth_unit="m")

    async def test_rejects_empty_curves(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="curves must be non-empty"):
            await knot.process(body=b"x", well_id="W-01", curves=(), depth_unit="m")

    async def test_rejects_invalid_depth_unit(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="depth_unit must be"):
            await knot.process(body=b"x", well_id="W-01", curves=("GR",), depth_unit="km")
