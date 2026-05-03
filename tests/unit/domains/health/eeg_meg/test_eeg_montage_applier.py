"""Unit tests for :class:`EEGMontageApplier`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.eeg_montage_applier import EEGMontageApplier
from pirn.tapestry import Tapestry


@knot
async def emit_eeg_data() -> dict[str, Any]:
    return {
        "channels": ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "EOG"],
        "data": [],
        "sample_rate_hz": 512.0,
    }


class TestConstruction:
    def test_rejects_non_knot_eeg_data(self) -> None:
        with pytest.raises(TypeError, match="eeg_data"):
            EEGMontageApplier(
                eeg_data="not-a-knot",  # type: ignore[arg-type]
                montage_name="standard_1020",
                reference="average",
                _config=KnotConfig(id="ma"),
            )

    def test_rejects_empty_montage_name(self) -> None:
        with Tapestry():
            e = emit_eeg_data(_config=KnotConfig(id="e"))
            with pytest.raises(ValueError, match="montage_name"):
                EEGMontageApplier(
                    eeg_data=e,
                    montage_name="",
                    reference="average",
                    _config=KnotConfig(id="ma"),
                )

    def test_rejects_invalid_reference(self) -> None:
        with Tapestry():
            e = emit_eeg_data(_config=KnotConfig(id="e"))
            with pytest.raises(ValueError, match="reference"):
                EEGMontageApplier(
                    eeg_data=e,
                    montage_name="standard_1020",
                    reference="unknown",
                    _config=KnotConfig(id="ma"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            e = emit_eeg_data(_config=KnotConfig(id="e"))
            EEGMontageApplier(
                eeg_data=e,
                montage_name="standard_1020",
                reference="average",
                _config=KnotConfig(id="ma"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ma"]
        assert isinstance(out, dict)
        assert "channels" in out
        assert "reference" in out
        assert "montage" in out
        assert out["reference"] == "average"
        assert out["montage"] == "standard_1020"

    async def test_drop_channels_removed(self) -> None:
        with Tapestry() as t:
            e = emit_eeg_data(_config=KnotConfig(id="e"))
            EEGMontageApplier(
                eeg_data=e,
                montage_name="standard_1020",
                reference="average",
                drop_channels=("EOG",),
                _config=KnotConfig(id="ma"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ma"]
        assert "EOG" not in out["channels"]
        assert "Fp1" in out["channels"]
