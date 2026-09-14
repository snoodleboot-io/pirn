"""Unit tests for :class:`VMDDecomposer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.types.wavelet_payload import WaveletPayload
from pirn_signal.wavelets.vmd_decomposer import VMDDecomposer
from tests.conftest import emit_signal_payload, make_signal_payload


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> VMDDecomposer:
        with Tapestry():
            k = VMDDecomposer.__new__(VMDDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_non_positive_mode_count(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, mode_count=0, bandwidth_constraint=1.0)  # type: ignore[arg-type]

    async def test_rejects_non_positive_bandwidth(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, mode_count=4, bandwidth_constraint=0)  # type: ignore[arg-type]

    async def test_rejects_unknown_backend(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaisesRegex(ValueError, "backend must be one of"):
            await k.process(
                signal=None,  # type: ignore[arg-type]
                mode_count=4,
                bandwidth_constraint=1.0,
                backend="scipy",
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_payload_with_numpy_backend(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            VMDDecomposer(
                signal=sig,
                mode_count=4,
                bandwidth_constraint=1.0,
                backend="numpy",
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletPayload)
        assert out.metadata.wavelet_name == "vmd"
        assert out.metadata.scale_count == 4
        assert len(out.data) == 4

    async def test_default_backend_is_vmdpy(self) -> None:
        k = self._bare_knot()
        payload = make_signal_payload()
        try:
            import vmdpy  # noqa: F401
        except ImportError:
            with self.assertRaisesRegex(ImportError, r"'vmdpy' is required.*pirn-signal\[signal\]"):
                await k.process(signal=payload, mode_count=4, bandwidth_constraint=1.0)
            return
        out = await k.process(signal=payload, mode_count=4, bandwidth_constraint=1.0)
        assert isinstance(out, WaveletPayload)
        assert out.metadata.scale_count == 4

    async def test_vmdpy_backend_raises_import_error_when_missing(self) -> None:
        try:
            import vmdpy  # noqa: F401

            self.skipTest("vmdpy is installed; cannot test the missing-dependency path")
        except ImportError:
            pass
        k = self._bare_knot()
        payload = make_signal_payload()
        with self.assertRaisesRegex(ImportError, r"'vmdpy' is required.*pirn-signal\[signal\]"):
            await k.process(
                signal=payload,
                mode_count=4,
                bandwidth_constraint=1.0,
                backend="vmdpy",
            )

    @staticmethod
    def _bare_knot() -> VMDDecomposer:
        with Tapestry():
            k = VMDDecomposer.__new__(VMDDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="w"))
        return k
