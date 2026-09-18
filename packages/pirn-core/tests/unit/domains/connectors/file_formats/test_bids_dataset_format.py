"""Tests for :class:`BidsDatasetFormat` — BIDS dataset zip format.

The codec itself needs no optional backend, so this module no longer skips
wholesale when ``pybids`` is absent — which is how a validator that validated
nothing went unnoticed (PIR-873). The ``validate=True`` tests stand a fake
``bids`` module in ``sys.modules`` and assert on the arguments it receives.
"""

from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest import mock
from unittest.mock import patch

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.bids_dataset_format import (
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


class FakeBidsLayout:
    """Records how ``BIDSLayout`` was called, and can refuse the tree."""

    calls: ClassVar[list[dict[str, Any]]] = []
    raises: ClassVar[Exception | None] = None

    def __init__(self, root: str, validate: bool = True) -> None:
        members = sorted(str(p.relative_to(root)) for p in Path(root).rglob("*") if p.is_file())
        FakeBidsLayout.calls.append({"root": root, "validate": validate, "members": members})
        if FakeBidsLayout.raises is not None:
            raise FakeBidsLayout.raises


def _fake_bids() -> mock._patch_dict:
    """Patch ``sys.modules`` so the lazy ``bids`` import resolves to the fake."""
    FakeBidsLayout.calls = []
    FakeBidsLayout.raises = None
    return mock.patch.dict(sys.modules, {"bids": SimpleNamespace(BIDSLayout=FakeBidsLayout)})


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


class TestBidsDatasetFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(BidsDatasetFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert BidsDatasetFormat().streaming is False

    def test_name(self) -> None:
        assert BidsDatasetFormat().name == "bids_dataset"

    def test_validation_is_off_by_default(self) -> None:
        assert BidsDatasetFormat().validate is False

    def test_validation_can_be_turned_on(self) -> None:
        assert BidsDatasetFormat(validate=True).validate is True

    def test_rejects_a_non_bool_validate(self) -> None:
        with self.assertRaisesRegex(TypeError, "validate must be bool"):
            BidsDatasetFormat(validate="yes")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


class TestBidsDatasetFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_decode_emits_file_records(self) -> None:
        payload = _make_bids_zip()
        records = await _decode_bytes(BidsDatasetFormat(), payload)
        assert len(records) == 3
        paths = {r["relative_path"] for r in records}
        assert "README" in paths
        assert "dataset_description.json" in paths

    async def test_decode_record_shape(self) -> None:
        payload = _make_bids_zip()
        records = await _decode_bytes(BidsDatasetFormat(), payload)
        for rec in records:
            assert "relative_path" in rec
            assert "content" in rec
            assert isinstance(rec["content"], bytes)

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


class TestBidsDatasetFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_payload_raises(self) -> None:
        fmt = BidsDatasetFormat()

        async def _iter():
            yield b"not a zip file at all"

        with self.assertRaisesRegex(ValueError, "zip"):
            async for _ in await fmt.read(_iter()):
                pass

    async def test_encode_non_bytes_content_raises(self) -> None:
        fmt = BidsDatasetFormat()

        async def _records():
            yield {"relative_path": "file.txt", "content": "not bytes"}

        with self.assertRaises(TypeError):
            async for _ in await fmt.write(_records()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency guard
# ---------------------------------------------------------------------------


class TestBidsDatasetFormatValidation(unittest.IsolatedAsyncioTestCase):
    async def test_decode_without_validate_never_touches_pybids(self) -> None:
        payload = _make_bids_zip()
        with patch.dict("sys.modules", {"bids": None}):
            records = await _decode_bytes(BidsDatasetFormat(), payload)
        assert len(records) == 3

    async def test_validate_runs_the_standard_checks_not_a_no_op(self) -> None:
        """``BIDSLayout(validate=False)`` turned the standard's own checks off."""
        payload = _make_bids_zip()
        with _fake_bids():
            await _decode_bytes(BidsDatasetFormat(validate=True), payload)
        assert len(FakeBidsLayout.calls) == 1
        assert FakeBidsLayout.calls[0]["validate"] is True

    async def test_validate_sees_every_decoded_member(self) -> None:
        payload = _make_bids_zip()
        with _fake_bids():
            await _decode_bytes(BidsDatasetFormat(validate=True), payload)
        assert FakeBidsLayout.calls[0]["members"] == [
            "README",
            "dataset_description.json",
            "sub-01/anat/sub-01_T1w.json",
        ]

    async def test_a_dataset_that_fails_the_standard_raises(self) -> None:
        """A layout failure used to be a RuntimeWarning a pipeline never saw."""
        payload = _make_bids_zip()
        with _fake_bids():
            FakeBidsLayout.raises = RuntimeError("dataset_description.json is missing")
            with self.assertRaisesRegex(ValueError, "does not satisfy the BIDS standard"):
                await _decode_bytes(BidsDatasetFormat(validate=True), payload)

    async def test_validate_without_pybids_raises_the_install_hint(self) -> None:
        """Asking for validation and silently not getting it is the bug (PIR-873)."""
        payload = _make_bids_zip()
        with patch.dict("sys.modules", {"bids": None}):
            with self.assertRaisesRegex(ImportError, r'pip install "pirn-core\[bids\]"'):
                await _decode_bytes(BidsDatasetFormat(validate=True), payload)
