"""Round-trip and validation tests for :class:`PytorchFormat`."""

from __future__ import annotations

import importlib.util
import unittest

import pytest

from pirn.backends._signer import _Signer
from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.pytorch_format import (
    PytorchFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

_HAS_TORCH = importlib.util.find_spec("torch") is not None


def _tiny_state_dict() -> dict:
    import torch
    return {"weight": torch.zeros(2, 2)}


class TestPytorchFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = PytorchFormat()
        assert fmt.weights_only is True
        assert fmt.signer is None
        assert fmt.allow_unsigned is False

    def test_unsigned_unsafe_combination_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PytorchFormat(weights_only=False)

    def test_unsafe_with_signer_allowed(self) -> None:
        fmt = PytorchFormat(
            weights_only=False, signer=_Signer.test_signer()
        )
        assert fmt.weights_only is False
        assert fmt.signer is not None

    def test_unsafe_with_explicit_opt_out_allowed(self) -> None:
        fmt = PytorchFormat(weights_only=False, allow_unsigned=True)
        assert fmt.weights_only is False
        assert fmt.allow_unsigned is True

    def test_non_bool_weights_only_rejected(self) -> None:
        with self.assertRaises(TypeError):
            PytorchFormat(weights_only="yes")  # type: ignore[arg-type]

    def test_invalid_signer_type_rejected(self) -> None:
        with self.assertRaises(TypeError):
            PytorchFormat(signer="not-a-signer")  # type: ignore[arg-type]


class TestPytorchFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert PytorchFormat().name == "pytorch"

    def test_streaming_property(self) -> None:
        assert PytorchFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(PytorchFormat(), BatchFileFormat)


class TestPytorchFormatValidation(unittest.IsolatedAsyncioTestCase):
    async def test_encode_empty_rejected(self) -> None:
        fmt = PytorchFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_encode_missing_state_dict_rejected(self) -> None:
        fmt = PytorchFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"wrong": 1}])

    async def test_decode_non_bytes_rejected(self) -> None:
        fmt = PytorchFormat()
        with self.assertRaises(TypeError):
            await fmt._decode_full("not-bytes")  # type: ignore[arg-type]


@pytest.mark.skipif(not _HAS_TORCH, reason="requires torch")
class TestPytorchFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        import torch
        fmt = PytorchFormat()
        state = _tiny_state_dict()
        payload = await FormatRoundTrip.encode(
            fmt, [{"state_dict": state}]
        )
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        recovered = decoded[0]["state_dict"]
        assert "weight" in recovered
        assert torch.equal(recovered["weight"], state["weight"])

    async def test_round_trip_signed(self) -> None:
        signer = _Signer.test_signer()
        fmt = PytorchFormat(signer=signer)
        state = _tiny_state_dict()
        payload = await FormatRoundTrip.encode(
            fmt, [{"state_dict": state}]
        )
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded[0]["metadata"]["signed"] is True

    async def test_signed_payload_rejects_tamper(self) -> None:
        signer = _Signer.test_signer()
        fmt = PytorchFormat(signer=signer)
        payload = await FormatRoundTrip.encode(
            fmt, [{"state_dict": _tiny_state_dict()}]
        )
        tampered = bytes(payload)
        tampered = tampered[:40] + bytes([tampered[40] ^ 0xFF]) + tampered[41:]
        with self.assertRaises(ValueError):
            await FormatRoundTrip.decode(fmt, tampered)
