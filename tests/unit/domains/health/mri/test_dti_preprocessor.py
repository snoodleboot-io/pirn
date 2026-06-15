"""Unit tests for :class:`DTIPreprocessor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_health.mri.dti_preprocessor import DTIPreprocessor

_CFG = KnotConfig(id="d")


def _make_knot() -> DTIPreprocessor:
    with Tapestry():
        dw = Parameter("dw", dict, default={}, _config=KnotConfig(id="dw"))
        bv = Parameter("bv", dict, default={}, _config=KnotConfig(id="bv"))
        bl = Parameter("bl", dict, default={}, _config=KnotConfig(id="bl"))
        return DTIPreprocessor(dwi_data=dw, bvec_file=bv, bval_file=bl, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_bool_eddy_correct(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "eddy_correct"):
            await knot.process(dwi_data={}, bvec_file={}, bval_file={}, eddy_correct="yes")  # type: ignore[arg-type]

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(dwi_data={}, bvec_file={}, bval_file={})
        assert isinstance(out, dict)
        assert "preprocessed_dwi_path" in out
        assert "n_directions" in out
        assert "b_values" in out
        assert "motion_outliers" in out
