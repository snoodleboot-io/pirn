"""Unit tests for :class:`MEGBeamformer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.health.eeg_meg.meg_beamformer import MEGBeamformer
from pirn.tapestry import Tapestry

_MEG_DATA: dict[str, Any] = {
    "n_channels": 306,
    "n_samples": 500,
    "sample_rate_hz": 1000.0,
}
_FORWARD_MODEL: dict[str, Any] = {
    "n_sources": 8000,
    "lead_field": [],
}


@knot
async def emit_meg_data() -> dict[str, Any]:
    return _MEG_DATA


@knot
async def emit_forward_model() -> dict[str, Any]:
    return _FORWARD_MODEL


def _make_knot() -> MEGBeamformer:
    with Tapestry():
        meg = emit_meg_data(_config=KnotConfig(id="meg"))
        fwd = emit_forward_model(_config=KnotConfig(id="fwd"))
        return MEGBeamformer(
            meg_data=meg,
            forward_model=fwd,
            regularization=0.05,
            pick_ori="max_power",
            _config=KnotConfig(id="bf"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_dict_meg_data(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(TypeError, "meg_data"):
            await knot_inst.process(meg_data="x", forward_model=_FORWARD_MODEL, regularization=0.05, pick_ori="max_power")  # type: ignore[arg-type]

    async def test_rejects_non_dict_forward_model(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(TypeError, "forward_model"):
            await knot_inst.process(meg_data=_MEG_DATA, forward_model="x", regularization=0.05, pick_ori="max_power")  # type: ignore[arg-type]

    async def test_rejects_negative_regularization(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(ValueError, "regularization"):
            await knot_inst.process(meg_data=_MEG_DATA, forward_model=_FORWARD_MODEL, regularization=-0.1, pick_ori="max_power")

    async def test_rejects_invalid_pick_ori(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(ValueError, "pick_ori"):
            await knot_inst.process(meg_data=_MEG_DATA, forward_model=_FORWARD_MODEL, regularization=0.05, pick_ori="unknown")

    async def test_returns_dict_with_required_keys(self) -> None:
        knot_inst = _make_knot()
        out = await knot_inst.process(meg_data=_MEG_DATA, forward_model=_FORWARD_MODEL, regularization=0.05, pick_ori="max_power")
        assert isinstance(out, dict)
        assert "source_power" in out
        assert "n_sources" in out
        assert "peak_source_index" in out
        assert out["n_sources"] == 8000
        assert len(out["source_power"]) == 8000
