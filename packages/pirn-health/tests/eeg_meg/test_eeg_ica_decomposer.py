"""Unit tests for :class:`EEGICADecomposer`."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

try:
    import sklearn  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("sklearn not installed") from _e

from typing import Any

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.tapestry import Tapestry

from pirn_health.eeg_meg.eeg_ica_decomposer import EEGICADecomposer

_RNG = np.random.default_rng(0)
# ICA identifies non-Gaussian sources only: mix five distinct non-Gaussian
# waveforms (sine, square, sawtooth, cubed sine, Laplace noise) into eight
# channels so FastICA has a well-posed problem and converges.
_T = np.linspace(0.0, 8.0, 2000)
_SOURCES = np.stack(
    [
        np.sin(2.0 * _T),
        np.sign(np.sin(3.0 * _T)),
        (1.7 * _T) % 1.0 - 0.5,
        np.sin(5.0 * _T) ** 3,
        _RNG.laplace(size=_T.size),
    ]
)
_MIXING = _RNG.uniform(0.5, 1.5, size=(8, 5))
_EEG_DATA: dict[str, Any] = {
    "n_channels": 8,
    "n_samples": 2000,
    "sample_rate_hz": 250.0,
    "data": (_MIXING @ _SOURCES).tolist(),
}


@KnotFactory.knot
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
            await knot_inst.process(
                eeg_data=_EEG_DATA, n_components=5, algorithm="fastica", max_iter=0
            )

    async def test_returns_dict_with_required_keys(self) -> None:
        knot_inst = _make_knot()
        out = await knot_inst.process(eeg_data=_EEG_DATA, n_components=5, algorithm="infomax")
        assert isinstance(out, dict)
        assert out["n_components"] == 5
        assert "mixing_matrix" in out
        assert "unmixing_matrix" in out
        assert "component_variances" in out
        assert len(out["component_variances"]) == 5

    async def test_raises_install_hint_without_sdk(self) -> None:
        with patch.dict(sys.modules, {"sklearn.decomposition": None}):
            with self.assertRaisesRegex(ImportError, r"pirn-health\[health\]"):
                await _make_knot().process(eeg_data=_EEG_DATA, n_components=5, algorithm="fastica")
