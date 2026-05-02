"""Round-trip and validation tests for :class:`GgufFormat`.

The ``gguf`` SDK is large and optional. Construction / metadata tests
run unconditionally; round-trip tests skip when the SDK is unavailable.
"""

from __future__ import annotations

import pytest

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.gguf_format import GgufFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestGgufFormatConstruction:
    def test_default_construction(self) -> None:
        fmt = GgufFormat()
        assert fmt.name == "gguf"


class TestGgufFormatBasics:
    def test_streaming_property(self) -> None:
        assert GgufFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(GgufFormat(), BatchFileFormat)


class TestGgufFormatValidation:
    @pytest.mark.asyncio
    async def test_decode_non_bytes_rejected(self) -> None:
        fmt = GgufFormat()
        # Async _decode_full direct call ensures the type guard fires
        # without needing the SDK installed.
        with pytest.raises(TypeError):
            await fmt._decode_full("not-bytes")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_encode_empty_rejected(self) -> None:
        fmt = GgufFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    @pytest.mark.asyncio
    async def test_encode_missing_keys_rejected(self) -> None:
        fmt = GgufFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(
                fmt, [{"metadata": {}, "tensors": []}]
            )


class TestGgufFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        gguf = pytest.importorskip("gguf")
        np = pytest.importorskip("numpy")
        fmt = GgufFormat()
        record = {
            "architecture": "test",
            "metadata": {"general.name": "pirn-test"},
            "tensors": [
                {
                    "name": "weight",
                    "data": np.zeros((2, 2), dtype=np.float32),
                }
            ],
        }
        payload = await FormatRoundTrip.encode(fmt, [record])
        # First 4 bytes are the GGUF magic ``GGUF``.
        assert payload[:4] == b"GGUF"
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        out = decoded[0]
        assert out["tensor_count"] == 1
        assert "weight" in out["tensor_names"]
        assert isinstance(out["metadata"], dict)
        # Use ``gguf`` symbol so the import isn't dead.
        assert hasattr(gguf, "GGUFReader")
