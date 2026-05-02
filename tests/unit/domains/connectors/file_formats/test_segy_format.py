"""Round-trip and validation tests for :class:`SegyFormat`."""

from __future__ import annotations

import pytest

pytest.importorskip("segyio")
pytest.importorskip("numpy")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.segy_format import SegyFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _trace_record(idx: int, n_samples: int = 8) -> dict:
    import struct
    values = [float(idx * 10 + i) for i in range(n_samples)]
    data = struct.pack(f">{n_samples}f", *values)
    return {
        "trace_index": idx,
        "header": {},
        "data": data,
    }


class TestSegyFormatConstruction:
    def test_name(self) -> None:
        assert SegyFormat().name == "segy"

    def test_streaming_false(self) -> None:
        assert SegyFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(SegyFormat(), BatchFileFormat)

    def test_invalid_sample_rate_raises(self) -> None:
        with pytest.raises(ValueError):
            SegyFormat(sample_rate=0)

    def test_negative_sample_rate_raises(self) -> None:
        with pytest.raises(ValueError):
            SegyFormat(sample_rate=-1)

    def test_sample_rate_property(self) -> None:
        fmt = SegyFormat(sample_rate=4000)
        assert fmt.sample_rate == 4000


class TestSegyFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_single_trace(self) -> None:
        fmt = SegyFormat()
        records = [_trace_record(0)]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["trace_index"] == 0

    @pytest.mark.asyncio
    async def test_round_trip_multiple_traces(self) -> None:
        fmt = SegyFormat()
        records = [_trace_record(i) for i in range(3)]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 3


class TestSegyFormatErrors:
    @pytest.mark.asyncio
    async def test_encode_empty_raises(self) -> None:
        fmt = SegyFormat()
        with pytest.raises(ValueError, match="empty"):
            await fmt._encode_full([])


class TestSegyFormatMissingDep:
    def test_import_error_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys
        monkeypatch.setitem(sys.modules, "segyio", None)  # type: ignore[arg-type]
        fmt = SegyFormat()
        with pytest.raises(ImportError, match="pirn\\[oilgas\\]"):
            fmt._load_segyio()
