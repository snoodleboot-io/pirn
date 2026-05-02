"""Tests for :class:`BidsDatasetFormat` — BIDS dataset zip format."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import patch

import pytest

pytest.importorskip("bids")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.bids_dataset_format import (
    BidsDatasetFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bids_zip() -> bytes:
    """Return a minimal BIDS-like zip bundle as bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dataset_description.json", b'{"Name": "TestDataset", "BIDSVersion": "1.7.0"}')
        zf.writestr("README", b"Test BIDS dataset")
        zf.writestr("sub-01/anat/sub-01_T1w.json", b'{"Manufacturer": "Siemens"}')
    return buf.getvalue()


async def _decode_bytes(fmt: BidsDatasetFormat, payload: bytes) -> list[dict]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestBidsDatasetFormatConstruction:
    def test_is_batch_format(self) -> None:
        assert isinstance(BidsDatasetFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert BidsDatasetFormat().streaming is False

    def test_name(self) -> None:
        assert BidsDatasetFormat().name == "bids_dataset"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestBidsDatasetFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_decode_emits_file_records(self) -> None:
        payload = _make_bids_zip()
        records = await _decode_bytes(BidsDatasetFormat(), payload)
        assert len(records) == 3
        paths = {r["relative_path"] for r in records}
        assert "README" in paths
        assert "dataset_description.json" in paths

    @pytest.mark.asyncio
    async def test_decode_record_shape(self) -> None:
        payload = _make_bids_zip()
        records = await _decode_bytes(BidsDatasetFormat(), payload)
        for rec in records:
            assert "relative_path" in rec
            assert "content" in rec
            assert isinstance(rec["content"], bytes)

    @pytest.mark.asyncio
    async def test_round_trip_preserves_content(self) -> None:
        payload = _make_bids_zip()
        fmt = BidsDatasetFormat()
        records = await _decode_bytes(fmt, payload)
        encoded = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(decoded) == len(records)
        original_by_path = {r["relative_path"]: r["content"] for r in records}
        recovered_by_path = {r["relative_path"]: r["content"] for r in decoded}
        assert original_by_path == recovered_by_path

    @pytest.mark.asyncio
    async def test_round_trip_two_files(self) -> None:
        records = [
            {"relative_path": "file_a.txt", "content": b"hello"},
            {"relative_path": "sub/file_b.nii", "content": b"\x00\x01\x02"},
        ]
        fmt = BidsDatasetFormat()
        encoded = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(decoded) == 2


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestBidsDatasetFormatErrors:
    @pytest.mark.asyncio
    async def test_invalid_payload_raises(self) -> None:
        fmt = BidsDatasetFormat()

        async def _iter():
            yield b"not a zip file at all"

        with pytest.raises(ValueError, match="zip"):
            async for _ in await fmt.read(_iter()):
                pass

    @pytest.mark.asyncio
    async def test_encode_non_bytes_content_raises(self) -> None:
        fmt = BidsDatasetFormat()

        async def _records():
            yield {"relative_path": "file.txt", "content": "not bytes"}

        with pytest.raises(TypeError):
            async for _ in await fmt.write(_records()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency guard
# ---------------------------------------------------------------------------

class TestBidsDatasetFormatMissingDep:
    def test_still_works_without_pybids(self) -> None:
        """Format should work even when pybids is absent (plain zip mode)."""
        with patch.dict("sys.modules", {"bids": None}):
            # No ImportError should be raised; validation is skipped
            BidsDatasetFormat._validate_bids_if_available([])
