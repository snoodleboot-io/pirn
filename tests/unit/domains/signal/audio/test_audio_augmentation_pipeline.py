"""Unit tests for :class:`AudioAugmentationPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.audio_augmentation_pipeline import AudioAugmentationPipeline
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_empty_augmentations(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="augmentations"):
                AudioAugmentationPipeline(
                    signal=sig,
                    augmentations=(),
                    seed=42,
                    _config=KnotConfig(id="aug"),
                )

    def test_rejects_unknown_augmentation(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="unknown"):
                AudioAugmentationPipeline(
                    signal=sig,
                    augmentations=("invalid_aug",),
                    seed=42,
                    _config=KnotConfig(id="aug"),
                )

    def test_rejects_negative_seed(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="seed"):
                AudioAugmentationPipeline(
                    signal=sig,
                    augmentations=("add_noise",),
                    seed=-1,
                    _config=KnotConfig(id="aug"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            aug = AudioAugmentationPipeline(
                signal=sig,
                augmentations=("pitch_shift", "add_noise"),
                seed=0,
                _config=KnotConfig(id="aug"),
            )
        assert aug.seed == 0
        assert "pitch_shift" in aug.augmentations


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            AudioAugmentationPipeline(
                signal=sig,
                augmentations=("add_noise",),
                seed=7,
                _config=KnotConfig(id="aug"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["aug"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1000.0
