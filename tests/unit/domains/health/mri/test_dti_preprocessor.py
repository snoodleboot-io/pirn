"""Unit tests for :class:`DTIPreprocessor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.dti_preprocessor import DTIPreprocessor
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        DTIPreprocessor(
            dwi_data=Parameter("dw", dict, default={}, _config=KnotConfig(id="dw")),
            bvec_file=Parameter("bv", dict, default={}, _config=KnotConfig(id="bv")),
            bval_file=Parameter("bl", dict, default={}, _config=KnotConfig(id="bl")),
            _config=KnotConfig(id="d"),
        )

    def test_rejects_non_bool_eddy_correct(self) -> None:
        with self.assertRaisesRegex(TypeError, "eddy_correct"):
            DTIPreprocessor(
                dwi_data=Parameter("dw", dict, default={}, _config=KnotConfig(id="dw")),
                bvec_file=Parameter("bv", dict, default={}, _config=KnotConfig(id="bv")),
                bval_file=Parameter("bl", dict, default={}, _config=KnotConfig(id="bl")),
                eddy_correct="yes",  # type: ignore[arg-type]
                _config=KnotConfig(id="d"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict(self) -> None:
        with Tapestry() as t:
            DTIPreprocessor(
                dwi_data=Parameter("dw", dict, default={}, _config=KnotConfig(id="dw")),
                bvec_file=Parameter("bv", dict, default={}, _config=KnotConfig(id="bv")),
                bval_file=Parameter("bl", dict, default={}, _config=KnotConfig(id="bl")),
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, dict)
        assert "preprocessed_dwi_path" in out
        assert "n_directions" in out
        assert "b_values" in out
        assert "motion_outliers" in out
