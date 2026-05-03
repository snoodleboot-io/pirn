"""Unit tests for :class:`BIDSConverter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.bids_converter import BIDSConverter
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_output_dir(self) -> None:
        with pytest.raises(ValueError, match="output_dir"):
            BIDSConverter(
                input_data=Parameter("inp", dict, default={}, _config=KnotConfig(id="inp")),
                output_dir="",
                modality="T1w",
                subject_id="001",
                _config=KnotConfig(id="b"),
            )

    def test_rejects_invalid_modality(self) -> None:
        with pytest.raises(ValueError, match="modality"):
            BIDSConverter(
                input_data=Parameter("inp", dict, default={}, _config=KnotConfig(id="inp")),
                output_dir="/bids",
                modality="CT",
                subject_id="001",
                _config=KnotConfig(id="b"),
            )

    def test_rejects_empty_subject_id(self) -> None:
        with pytest.raises(ValueError, match="subject_id"):
            BIDSConverter(
                input_data=Parameter("inp", dict, default={}, _config=KnotConfig(id="inp")),
                output_dir="/bids",
                modality="T1w",
                subject_id="",
                _config=KnotConfig(id="b"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict(self) -> None:
        data = {"nifti_path": "sub.nii.gz", "metadata": {}}
        with Tapestry() as t:
            BIDSConverter(
                input_data=Parameter("inp", dict, default=data, _config=KnotConfig(id="inp")),
                output_dir="/bids",
                modality="T1w",
                subject_id="001",
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, dict)
        assert out["subject_id"] == "001"
        assert out["modality"] == "T1w"
        assert "bids_path" in out
