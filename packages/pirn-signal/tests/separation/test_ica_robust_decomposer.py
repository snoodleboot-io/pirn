"""Unit tests for :class:`ICARobustDecomposer`."""

from __future__ import annotations

import unittest

try:
    import sklearn  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("sklearn not installed") from _e

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.separation.ica_robust_decomposer import ICARobustDecomposer
from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_payload import SourcePayload

_rng = np.random.default_rng(0)
_SIGNAL = SignalPayload(
    metadata=SignalFrame(
        signal_id="test", channel_count=8, sample_rate_hz=1000.0, samples_per_channel=1024
    ),
    data=_rng.standard_normal((8, 1024)),
)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestICARobustDecomposer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ICARobustDecomposer:
        return ICARobustDecomposer(
            signal=_up(),
            source_count=3,
            contamination_fraction=0.1,
            _config=KnotConfig(id="rica"),
        )

    async def test_rejects_non_positive_source_count(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="source_count"):
            await knot.process(_SIGNAL, source_count=0, contamination_fraction=0.1)

    async def test_rejects_contamination_ge_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="contamination_fraction"):
            await knot.process(_SIGNAL, source_count=3, contamination_fraction=1.0)

    async def test_emits_source_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, source_count=3, contamination_fraction=0.1)
        assert isinstance(out, SourcePayload)
        assert out.metadata.source_count == 3


class TestContaminationFractionIsUsed(unittest.IsolatedAsyncioTestCase):
    """The declared outlier fraction is excluded from the unmixing fit."""

    @staticmethod
    def _contaminated_mixture() -> tuple[SignalPayload, np.ndarray, np.ndarray]:
        """Two mixed sources, 5 % of the samples replaced by gross outliers.

        Returns the payload, the true sources, and the mask of uncontaminated samples.
        """
        rng = np.random.default_rng(11)
        sample_count = 600
        time = np.linspace(0.0, 8.0, sample_count)
        sources = np.vstack([np.sin(2.0 * time), np.sign(np.sin(3.0 * time))])
        mixing = np.array([[0.8, 0.4], [0.3, 0.9]])
        observations = mixing @ sources
        outliers = rng.choice(sample_count, size=30, replace=False)
        observations[:, outliers] += 40.0 * rng.standard_normal((2, 30))
        clean = np.ones(sample_count, dtype=bool)
        clean[outliers] = False
        payload = SignalPayload(
            metadata=SignalFrame(
                signal_id="test",
                channel_count=2,
                sample_rate_hz=100.0,
                samples_per_channel=sample_count,
            ),
            data=observations,
        )
        return payload, sources, clean

    @staticmethod
    def _best_match(estimates: np.ndarray, sources: np.ndarray) -> float:
        """Mean best absolute correlation between each true source and some estimate."""
        total = 0.0
        for source in sources:
            correlations = [
                abs(float(np.corrcoef(estimate, source)[0, 1])) for estimate in estimates
            ]
            total += max(correlations)
        return total / len(sources)

    def _knot(self) -> ICARobustDecomposer:
        return ICARobustDecomposer(
            signal=_up(),
            source_count=2,
            contamination_fraction=0.1,
            _config=KnotConfig(id="icar"),
        )

    async def test_trimming_the_outliers_recovers_the_sources_better(self) -> None:
        # Arrange
        payload, sources, clean = self._contaminated_mixture()
        knot = self._knot()

        # Act
        untrimmed = await knot.process(signal=payload, source_count=2, contamination_fraction=0.0)
        trimmed = await knot.process(signal=payload, source_count=2, contamination_fraction=0.1)

        # Assert: on the samples that were never contaminated, the unmixing fitted
        # without the outliers reconstructs the sources better than the one fitted
        # with them — the whole point of the declared contamination fraction.
        untrimmed_match = self._best_match(
            np.asarray(untrimmed.data, dtype=float)[:, clean], sources[:, clean]
        )
        trimmed_match = self._best_match(
            np.asarray(trimmed.data, dtype=float)[:, clean], sources[:, clean]
        )
        assert trimmed_match > untrimmed_match, (trimmed_match, untrimmed_match)
        assert trimmed_match > 0.99, trimmed_match
