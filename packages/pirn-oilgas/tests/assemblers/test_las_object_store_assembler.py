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

from pirn_oilgas.assemblers.las_object_store_assembler import LasObjectStoreAssembler
from pirn_oilgas.types.las_file import LASFile
from pirn_oilgas.types.las_payload import LASPayload


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
            "pirn_oilgas.assemblers.las_object_store_assembler.LasObjectStoreAssembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(
                body=b"las-bytes", well_id="W-01", curves=("GR", "RHOB"), depth_unit="m"
            )
        assert isinstance(result, LASPayload)

    async def test_metadata_well_id_matches(self) -> None:
        knot = _make("W-01")
        with patch(
            "pirn_oilgas.assemblers.las_object_store_assembler.LasObjectStoreAssembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(
                body=b"las-bytes", well_id="W-01", curves=("GR", "RHOB"), depth_unit="m"
            )
        assert result.metadata.well_id == "W-01"

    async def test_metadata_curves_populated(self) -> None:
        knot = _make("W-01")
        with patch(
            "pirn_oilgas.assemblers.las_object_store_assembler.LasObjectStoreAssembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(
                body=b"las-bytes", well_id="W-01", curves=("GR", "RHOB"), depth_unit="m"
            )
        assert result.metadata.curves == ("GR", "RHOB")

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


_LAS_2_0 = """~VERSION INFORMATION
 VERS.                 2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0
 WRAP.                  NO : ONE LINE PER DEPTH STEP
~WELL INFORMATION
 STRT.M             1000.0 : START DEPTH
 STOP.M             1002.0 : STOP DEPTH
 STEP.M                0.5 : STEP
 NULL.             -999.25 : NULL VALUE
 WELL.               W-01  : WELL
~CURVE INFORMATION
 DEPT.M                    : DEPTH
 GR  .GAPI                 : GAMMA RAY
~ASCII
 1000.0   45.5
 1000.5   52.25
 1001.0   61.0
 1001.5   38.75
 1002.0   44.0
"""


class TestDecodesRealLasBytes(unittest.IsolatedAsyncioTestCase):
    """The decode path itself, not a patched stand-in."""

    async def test_requested_curve_carries_the_logged_values(self) -> None:
        knot = _make("W-01")

        result = await knot.process(
            body=_LAS_2_0.encode("utf-8"), well_id="W-01", curves=("GR",), depth_unit="m"
        )

        np.testing.assert_allclose(result.data["GR"], [45.5, 52.25, 61.0, 38.75, 44.0])

    async def test_curve_absent_from_the_file_raises_instead_of_zeros(self) -> None:
        """A zero RHOB curve would read downstream as a real, valid measurement."""
        knot = _make("W-01")

        with pytest.raises(ValueError, match="no curve"):
            await knot.process(
                body=_LAS_2_0.encode("utf-8"),
                well_id="W-01",
                curves=("GR", "RHOB"),
                depth_unit="m",
            )
