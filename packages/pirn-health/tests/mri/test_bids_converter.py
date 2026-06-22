"""Unit tests for :class:`BIDSConverter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_health.mri.bids_converter import BIDSConverter

_CFG = KnotConfig(id="b")
_DATA = {"nifti_path": "sub.nii.gz", "metadata": {}}


def _make_knot() -> BIDSConverter:
    with Tapestry():
        src = Parameter("inp", dict, default=_DATA, _config=KnotConfig(id="inp"))
        return BIDSConverter(input_data=src, output_dir="/bids", modality="T1w", subject_id="001", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_output_dir(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "output_dir"):
            await knot.process(input_data=_DATA, output_dir="", modality="T1w", subject_id="001")

    async def test_rejects_invalid_modality(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "modality"):
            await knot.process(input_data=_DATA, output_dir="/bids", modality="CT", subject_id="001")

    async def test_rejects_empty_subject_id(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "subject_id"):
            await knot.process(input_data=_DATA, output_dir="/bids", modality="T1w", subject_id="")

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(input_data=_DATA, output_dir="/bids", modality="T1w", subject_id="001")
        assert isinstance(out, dict)
        assert out["subject_id"] == "001"
        assert out["modality"] == "T1w"
        assert "bids_path" in out
