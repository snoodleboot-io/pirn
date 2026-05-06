"""Unit tests for :class:`EEGMontageApplier`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.health.eeg_meg.eeg_montage_applier import EEGMontageApplier
from pirn.tapestry import Tapestry

_EEG_DATA: dict[str, Any] = {
    "channels": ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "EOG"],
    "data": [],
    "sample_rate_hz": 512.0,
}


@knot
async def emit_eeg_data() -> dict[str, Any]:
    return _EEG_DATA


def _make_knot() -> EEGMontageApplier:
    with Tapestry():
        e = emit_eeg_data(_config=KnotConfig(id="e"))
        return EEGMontageApplier(
            eeg_data=e,
            montage_name="standard_1020",
            reference="average",
            _config=KnotConfig(id="ma"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_dict_eeg_data(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(TypeError, "dict"):
            await knot_inst.process(eeg_data="not-a-dict", montage_name="standard_1020", reference="average")  # type: ignore[arg-type]

    async def test_rejects_empty_montage_name(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(ValueError, "montage_name"):
            await knot_inst.process(eeg_data=_EEG_DATA, montage_name="", reference="average")

    async def test_rejects_invalid_reference(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(ValueError, "reference"):
            await knot_inst.process(eeg_data=_EEG_DATA, montage_name="standard_1020", reference="unknown")

    async def test_returns_dict_with_required_keys(self) -> None:
        knot_inst = _make_knot()
        out = await knot_inst.process(eeg_data=_EEG_DATA, montage_name="standard_1020", reference="average")
        assert isinstance(out, dict)
        assert "channels" in out
        assert "reference" in out
        assert "montage" in out
        assert out["reference"] == "average"
        assert out["montage"] == "standard_1020"

    async def test_drop_channels_removed(self) -> None:
        knot_inst = _make_knot()
        out = await knot_inst.process(
            eeg_data=_EEG_DATA,
            montage_name="standard_1020",
            reference="average",
            drop_channels=("EOG",),
        )
        assert "EOG" not in out["channels"]
        assert "Fp1" in out["channels"]
