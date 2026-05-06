"""Unit tests for :class:`EEGICADecomposer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.health.eeg_meg.eeg_ica_decomposer import EEGICADecomposer
from pirn.tapestry import Tapestry

_EEG_DATA: dict[str, Any] = {
    "n_channels": 64,
    "n_samples": 1000,
    "sample_rate_hz": 250.0,
    "data": [],
}


@knot
async def emit_eeg_data() -> dict[str, Any]:
    return _EEG_DATA


def _make_knot() -> EEGICADecomposer:
    with Tapestry():
        e = emit_eeg_data(_config=KnotConfig(id="e"))
        return EEGICADecomposer(
            eeg_data=e,
            n_components=5,
            algorithm="fastica",
            _config=KnotConfig(id="ica"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_dict_eeg_data(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(TypeError, "dict"):
            await knot_inst.process(eeg_data="not-a-dict", n_components=5, algorithm="fastica")  # type: ignore[arg-type]

    async def test_rejects_non_positive_n_components(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(ValueError, "n_components"):
            await knot_inst.process(eeg_data=_EEG_DATA, n_components=0, algorithm="fastica")

    async def test_rejects_invalid_algorithm(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(ValueError, "algorithm"):
            await knot_inst.process(eeg_data=_EEG_DATA, n_components=5, algorithm="unknown")

    async def test_rejects_non_positive_max_iter(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(ValueError, "max_iter"):
            await knot_inst.process(eeg_data=_EEG_DATA, n_components=5, algorithm="fastica", max_iter=0)

    async def test_returns_dict_with_required_keys(self) -> None:
        knot_inst = _make_knot()
        out = await knot_inst.process(eeg_data=_EEG_DATA, n_components=5, algorithm="infomax")
        assert isinstance(out, dict)
        assert out["n_components"] == 5
        assert "mixing_matrix" in out
        assert "unmixing_matrix" in out
        assert "component_variances" in out
        assert len(out["component_variances"]) == 5
