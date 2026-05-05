"""Unit tests for :class:`AudioFeatureExtractor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.audio_feature_extractor import AudioFeatureExtractor
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_n_mfcc(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "n_mfcc"):
                AudioFeatureExtractor(
                    signal=sig,
                    n_mfcc=0,
                    n_fft=512,
                    hop_length=128,
                    _config=KnotConfig(id="fe"),
                )

    def test_rejects_non_positive_n_fft(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "n_fft"):
                AudioFeatureExtractor(
                    signal=sig,
                    n_mfcc=13,
                    n_fft=0,
                    hop_length=128,
                    _config=KnotConfig(id="fe"),
                )

    def test_rejects_non_positive_hop_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "hop_length"):
                AudioFeatureExtractor(
                    signal=sig,
                    n_mfcc=13,
                    n_fft=512,
                    hop_length=0,
                    _config=KnotConfig(id="fe"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            fe = AudioFeatureExtractor(
                signal=sig,
                n_mfcc=13,
                n_fft=512,
                hop_length=128,
                _config=KnotConfig(id="fe"),
            )
        assert fe.n_mfcc == 13
        assert fe.n_fft == 512
        assert fe.hop_length == 128


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_feature_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            AudioFeatureExtractor(
                signal=sig,
                n_mfcc=13,
                n_fft=512,
                hop_length=128,
                _config=KnotConfig(id="fe"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fe"]
        assert isinstance(out, dict)
        assert "rms_energy" in out
        assert "mfcc_mean" in out
