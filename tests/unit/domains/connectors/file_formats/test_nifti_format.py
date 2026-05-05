"""Tests for :class:`NiftiFormat` — NIfTI neuroimaging format."""

from __future__ import annotations

from unittest.mock import patch
import unittest


try:
    import nibabel
except ImportError as _e:
    raise unittest.SkipTest("nibabel not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.nifti_format import NiftiFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_nifti_bytes() -> bytes:
    """Return a minimal valid NIfTI file as bytes."""
    import tempfile
    from pathlib import Path

    import nibabel as nib
    import numpy as np

    data = np.zeros((4, 4, 4), dtype=np.float32)
    data[1, 1, 1] = 1.0
    import io as _io

    affine = np.eye(4)
    img = nib.Nifti1Image(data, affine)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "image.nii"
        nib.save(img, str(path))
        return path.read_bytes()


async def _decode_bytes(fmt: NiftiFormat, payload: bytes) -> list[dict]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestNiftiFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(NiftiFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert NiftiFormat().streaming is False

    def test_name(self) -> None:
        assert NiftiFormat().name == "nifti"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestNiftiFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_decode_record_shape(self) -> None:
        payload = _make_nifti_bytes()
        records = await _decode_bytes(NiftiFormat(), payload)
        assert len(records) == 1
        record = records[0]
        assert "shape" in record
        assert "dtype" in record
        assert "affine" in record
        assert "header" in record
        assert "data" in record

    async def test_round_trip_preserves_shape_and_data(self) -> None:
        import numpy as np

        payload = _make_nifti_bytes()
        fmt = NiftiFormat()
        records = await _decode_bytes(fmt, payload)
        assert records[0]["shape"] == (4, 4, 4)
        # Re-encode and decode again
        encoded = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert decoded[0]["shape"] == (4, 4, 4)
        original_arr = np.frombuffer(records[0]["data"], dtype=records[0]["dtype"])
        recovered_arr = np.frombuffer(decoded[0]["data"], dtype=decoded[0]["dtype"])
        assert np.allclose(original_arr, recovered_arr)

    async def test_decode_affine_is_list_of_lists(self) -> None:
        payload = _make_nifti_bytes()
        records = await _decode_bytes(NiftiFormat(), payload)
        affine = records[0]["affine"]
        assert isinstance(affine, list)
        assert isinstance(affine[0], list)

    async def test_decode_data_is_bytes(self) -> None:
        payload = _make_nifti_bytes()
        records = await _decode_bytes(NiftiFormat(), payload)
        assert isinstance(records[0]["data"], bytes)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestNiftiFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_encode_empty_raises(self) -> None:
        fmt = NiftiFormat()

        async def _empty():
            return
            yield

        with self.assertRaisesRegex(ValueError, "empty"):
            async for _ in await fmt.write(_empty()):
                pass

    async def test_encode_invalid_data_type_raises(self) -> None:
        fmt = NiftiFormat()

        async def _records():
            yield {
                "shape": (1, 1, 1),
                "dtype": "float32",
                "affine": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                "header": {},
                "data": "not bytes",
            }

        with self.assertRaises(TypeError):
            async for _ in await fmt.write(_records()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency guard
# ---------------------------------------------------------------------------

class TestNiftiFormatMissingDep(unittest.TestCase):
    def test_load_nibabel_raises_on_missing(self) -> None:
        with patch.dict("sys.modules", {"nibabel": None}):
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                NiftiFormat._load_nibabel()
