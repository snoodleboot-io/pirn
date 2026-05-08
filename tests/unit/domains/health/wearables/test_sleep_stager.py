"""Unit tests for :class:`SleepStager`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload
from pirn.domains.health.wearables.sleep_stager import SleepStager
from pirn.tapestry import Tapestry

_SLEEP_SIGNAL = SignalPayload(
    frame=SignalFrame(signal_id="sleep", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        inst = object.__new__(SleepStager)
        with self.assertRaisesRegex(TypeError, "SignalPayload"):
            await SleepStager.process(
                inst,
                signal="x",  # type: ignore[arg-type]
                epoch_length_sec=30.0,
            )

    async def test_rejects_non_numeric(self) -> None:
        inst = object.__new__(SleepStager)
        with self.assertRaisesRegex(TypeError, "epoch_length_sec"):
            await SleepStager.process(
                inst,
                signal=_SLEEP_SIGNAL,
                epoch_length_sec="x",  # type: ignore[arg-type]
            )

    async def test_rejects_non_positive(self) -> None:
        inst = object.__new__(SleepStager)
        with self.assertRaisesRegex(ValueError, "positive"):
            await SleepStager.process(
                inst,
                signal=_SLEEP_SIGNAL,
                epoch_length_sec=0.0,
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_stages_tuple(self) -> None:
        with Tapestry() as t:
            SleepStager(
                signal=SignalPayload(
                    frame=SignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
                    data=np.random.default_rng(0).standard_normal((2, 512)),
                ),
                epoch_length_sec=30.0,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, tuple)
        assert all(isinstance(x, str) for x in out)
