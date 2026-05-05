"""Unit tests for :class:`MEGBeamformer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.meg_beamformer import MEGBeamformer
from pirn.tapestry import Tapestry


@knot
async def emit_meg_data() -> dict[str, Any]:
    return {
        "n_channels": 306,
        "n_samples": 500,
        "sample_rate_hz": 1000.0,
    }


@knot
async def emit_forward_model() -> dict[str, Any]:
    return {
        "n_sources": 8000,
        "lead_field": [],
    }


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_meg_data(self) -> None:
        with Tapestry():
            fwd = emit_forward_model(_config=KnotConfig(id="fwd"))
            with self.assertRaisesRegex(TypeError, "meg_data"):
                MEGBeamformer(
                    meg_data="not-a-knot",  # type: ignore[arg-type]
                    forward_model=fwd,
                    regularization=0.05,
                    pick_ori="max_power",
                    _config=KnotConfig(id="bf"),
                )

    def test_rejects_non_knot_forward_model(self) -> None:
        with Tapestry():
            meg = emit_meg_data(_config=KnotConfig(id="meg"))
            with self.assertRaisesRegex(TypeError, "forward_model"):
                MEGBeamformer(
                    meg_data=meg,
                    forward_model="not-a-knot",  # type: ignore[arg-type]
                    regularization=0.05,
                    pick_ori="max_power",
                    _config=KnotConfig(id="bf"),
                )

    def test_rejects_negative_regularization(self) -> None:
        with Tapestry():
            meg = emit_meg_data(_config=KnotConfig(id="meg"))
            fwd = emit_forward_model(_config=KnotConfig(id="fwd"))
            with self.assertRaisesRegex(ValueError, "regularization"):
                MEGBeamformer(
                    meg_data=meg,
                    forward_model=fwd,
                    regularization=-0.1,
                    pick_ori="max_power",
                    _config=KnotConfig(id="bf"),
                )

    def test_rejects_invalid_pick_ori(self) -> None:
        with Tapestry():
            meg = emit_meg_data(_config=KnotConfig(id="meg"))
            fwd = emit_forward_model(_config=KnotConfig(id="fwd"))
            with self.assertRaisesRegex(ValueError, "pick_ori"):
                MEGBeamformer(
                    meg_data=meg,
                    forward_model=fwd,
                    regularization=0.05,
                    pick_ori="unknown",
                    _config=KnotConfig(id="bf"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            meg = emit_meg_data(_config=KnotConfig(id="meg"))
            fwd = emit_forward_model(_config=KnotConfig(id="fwd"))
            MEGBeamformer(
                meg_data=meg,
                forward_model=fwd,
                regularization=0.05,
                pick_ori="max_power",
                _config=KnotConfig(id="bf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["bf"]
        assert isinstance(out, dict)
        assert "source_power" in out
        assert "n_sources" in out
        assert "peak_source_index" in out
        assert out["n_sources"] == 8000
        assert len(out["source_power"]) == 8000
