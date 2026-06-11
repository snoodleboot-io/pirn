"""Unit tests for :class:`StepCounter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.types.health_signal_frame import HealthSignalFrame
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload
from pirn.domains.health.wearables.step_counter import StepCounter
from pirn.tapestry import Tapestry

_STEP_SIGNAL = HealthSignalPayload(
    metadata=HealthSignalFrame(signal_id="steps", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        inst = object.__new__(StepCounter)
        with self.assertRaisesRegex(TypeError, "HealthSignalPayload"):
            await StepCounter.process(
                inst,
                signal="x",  # type: ignore[arg-type]
                threshold=0.5,
            )

    async def test_rejects_negative_threshold(self) -> None:
        inst = object.__new__(StepCounter)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            await StepCounter.process(
                inst,
                signal=_STEP_SIGNAL,
                threshold=-0.1,
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_int(self) -> None:
        with Tapestry() as t:
            StepCounter(
                signal=_STEP_SIGNAL,
                threshold=1.0,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, int)
