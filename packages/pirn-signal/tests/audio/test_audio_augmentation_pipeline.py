"""Unit tests for :class:`AudioAugmentationPipeline`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.audio.audio_augmentation_pipeline import AudioAugmentationPipeline
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestAudioAugmentationPipeline(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> AudioAugmentationPipeline:
        return AudioAugmentationPipeline(
            signal=_up(),
            augmentations=("add_noise",),
            seed=42,
            _config=KnotConfig(id="aug"),
        )

    async def test_rejects_empty_augmentations(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="augmentations"):
            await knot.process(_SIGNAL, augmentations=(), seed=42)

    async def test_rejects_unknown_augmentation(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError):
            await knot.process(_SIGNAL, augmentations=("unknown",), seed=42)

    async def test_rejects_negative_seed(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="seed"):
            await knot.process(_SIGNAL, augmentations=("add_noise",), seed=-1)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, augmentations=("add_noise",), seed=0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:augmented"
