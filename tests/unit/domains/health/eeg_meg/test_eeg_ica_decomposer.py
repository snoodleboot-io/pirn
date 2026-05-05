"""Unit tests for :class:`EEGICADecomposer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.eeg_ica_decomposer import EEGICADecomposer
from pirn.tapestry import Tapestry


@knot
async def emit_eeg_data() -> dict[str, Any]:
    return {
        "n_channels": 64,
        "n_samples": 1000,
        "sample_rate_hz": 250.0,
        "data": [],
    }


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_eeg_data(self) -> None:
        with self.assertRaisesRegex(TypeError, "eeg_data"):
            EEGICADecomposer(
                eeg_data="not-a-knot",  # type: ignore[arg-type]
                n_components=20,
                algorithm="fastica",
                _config=KnotConfig(id="ica"),
            )

    def test_rejects_non_positive_n_components(self) -> None:
        with Tapestry():
            e = emit_eeg_data(_config=KnotConfig(id="e"))
            with self.assertRaisesRegex(ValueError, "n_components"):
                EEGICADecomposer(
                    eeg_data=e,
                    n_components=0,
                    algorithm="fastica",
                    _config=KnotConfig(id="ica"),
                )

    def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            e = emit_eeg_data(_config=KnotConfig(id="e"))
            with self.assertRaisesRegex(ValueError, "algorithm"):
                EEGICADecomposer(
                    eeg_data=e,
                    n_components=20,
                    algorithm="unknown",
                    _config=KnotConfig(id="ica"),
                )

    def test_rejects_non_positive_max_iter(self) -> None:
        with Tapestry():
            e = emit_eeg_data(_config=KnotConfig(id="e"))
            with self.assertRaisesRegex(ValueError, "max_iter"):
                EEGICADecomposer(
                    eeg_data=e,
                    n_components=20,
                    algorithm="fastica",
                    max_iter=0,
                    _config=KnotConfig(id="ica"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            e = emit_eeg_data(_config=KnotConfig(id="e"))
            EEGICADecomposer(
                eeg_data=e,
                n_components=5,
                algorithm="infomax",
                _config=KnotConfig(id="ica"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ica"]
        assert isinstance(out, dict)
        assert out["n_components"] == 5
        assert "mixing_matrix" in out
        assert "unmixing_matrix" in out
        assert "component_variances" in out
        assert len(out["component_variances"]) == 5
