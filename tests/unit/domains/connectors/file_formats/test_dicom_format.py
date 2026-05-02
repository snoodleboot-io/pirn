"""Tests for :class:`DicomFormat` — DICOM medical imaging format."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("pydicom")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.dicom_format import DicomFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_dicom_bytes() -> bytes:
    """Return a minimal valid DICOM Part-10 file as bytes."""
    import pydicom
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    file_meta = FileMetaDataset()
    sop_uid = generate_uid()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = file_meta
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.SOPInstanceUID = sop_uid
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = "CT"
    ds.PatientID = "PATIENT123"
    ds.PatientName = "Smith^John"
    ds.PatientBirthDate = "19800101"
    ds.Rows = 2
    ds.Columns = 2
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = bytes([10, 20, 30, 40])

    buf = io.BytesIO()
    try:
        pydicom.dcmwrite(buf, ds, enforce_file_format=True)
    except TypeError:
        pydicom.dcmwrite(buf, ds, write_like_original=False)
    return buf.getvalue()


async def _decode_bytes(fmt: DicomFormat, payload: bytes) -> list[Mapping[str, Any]]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestDicomFormatConstruction:
    def test_is_batch_format(self) -> None:
        assert isinstance(DicomFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert DicomFormat().streaming is False

    def test_name(self) -> None:
        assert DicomFormat().name == "dicom"


# ---------------------------------------------------------------------------
# PHI keyword set
# ---------------------------------------------------------------------------

class TestPhiKeywords:
    def test_patient_id_in_phi_set(self) -> None:
        assert "PatientID" in DicomFormat._phi_keywords

    def test_patient_name_in_phi_set(self) -> None:
        assert "PatientName" in DicomFormat._phi_keywords

    def test_patient_birth_date_in_phi_set(self) -> None:
        assert "PatientBirthDate" in DicomFormat._phi_keywords

    def test_patient_address_in_phi_set(self) -> None:
        assert "PatientAddress" in DicomFormat._phi_keywords

    def test_phi_set_is_frozenset(self) -> None:
        assert isinstance(DicomFormat._phi_keywords, frozenset)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class TestHashPatientId:
    def test_known_hash(self) -> None:
        expected = hashlib.sha256(b"PATIENT123").hexdigest()
        assert DicomFormat._hash_patient_id("PATIENT123") == expected

    def test_empty_string(self) -> None:
        expected = hashlib.sha256(b"").hexdigest()
        assert DicomFormat._hash_patient_id("") == expected

    def test_unicode_patient_id(self) -> None:
        pid = "患者001"
        expected = hashlib.sha256(pid.encode("utf-8")).hexdigest()
        assert DicomFormat._hash_patient_id(pid) == expected


class TestCoerceShape:
    def test_none_returns_1_1(self) -> None:
        assert DicomFormat._coerce_shape(None) == (1, 1)

    def test_2d_tuple(self) -> None:
        assert DicomFormat._coerce_shape((128, 256)) == (128, 256)

    def test_3d_tuple_uses_first_two(self) -> None:
        assert DicomFormat._coerce_shape((64, 64, 3)) == (64, 64)

    def test_zero_rows_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            DicomFormat._coerce_shape((0, 128))

    def test_zero_cols_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            DicomFormat._coerce_shape((128, 0))

    def test_non_sequence_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            DicomFormat._coerce_shape("bad")


class TestCoerceMetadataValue:
    def test_string_passthrough(self) -> None:
        assert DicomFormat._coerce_metadata_value("hello") == "hello"

    def test_int_passthrough(self) -> None:
        assert DicomFormat._coerce_metadata_value(42) == 42

    def test_none_passthrough(self) -> None:
        assert DicomFormat._coerce_metadata_value(None) is None

    def test_bytes_become_repr(self) -> None:
        result = DicomFormat._coerce_metadata_value(b"\x00\x01")
        assert result == "<2 bytes>"

    def test_iterable_becomes_tuple(self) -> None:
        result = DicomFormat._coerce_metadata_value([1, 2, 3])
        assert result == ("1", "2", "3")


# ---------------------------------------------------------------------------
# Decode — PHI sanitisation
# ---------------------------------------------------------------------------

class TestDicomDecodePhiSanitisation:
    @pytest.mark.asyncio
    async def test_patient_id_hashed_not_raw(self) -> None:
        payload = _make_minimal_dicom_bytes()
        records = await _decode_bytes(DicomFormat(), payload)
        assert len(records) == 1
        record = records[0]
        expected_hash = hashlib.sha256(b"PATIENT123").hexdigest()
        assert record["patient_id_hash"] == expected_hash
        assert "patient_id" not in record

    @pytest.mark.asyncio
    async def test_patient_name_stripped_from_metadata(self) -> None:
        payload = _make_minimal_dicom_bytes()
        records = await _decode_bytes(DicomFormat(), payload)
        metadata = records[0]["metadata"]
        assert "PatientName" not in metadata

    @pytest.mark.asyncio
    async def test_patient_birth_date_stripped(self) -> None:
        payload = _make_minimal_dicom_bytes()
        records = await _decode_bytes(DicomFormat(), payload)
        metadata = records[0]["metadata"]
        assert "PatientBirthDate" not in metadata

    @pytest.mark.asyncio
    async def test_pixel_data_not_in_metadata(self) -> None:
        payload = _make_minimal_dicom_bytes()
        records = await _decode_bytes(DicomFormat(), payload)
        metadata = records[0]["metadata"]
        assert "PixelData" not in metadata

    @pytest.mark.asyncio
    async def test_non_phi_fields_present_in_metadata(self) -> None:
        payload = _make_minimal_dicom_bytes()
        records = await _decode_bytes(DicomFormat(), payload)
        metadata = records[0]["metadata"]
        assert "Modality" in metadata

    @pytest.mark.asyncio
    async def test_record_shape(self) -> None:
        payload = _make_minimal_dicom_bytes()
        records = await _decode_bytes(DicomFormat(), payload)
        record = records[0]
        assert "sop_instance_uid" in record
        assert "patient_id_hash" in record
        assert "study_uid" in record
        assert "series_uid" in record
        assert "modality" in record
        assert "pixel_array_shape" in record
        assert "pixel_data" in record
        assert "metadata" in record

    @pytest.mark.asyncio
    async def test_modality_ct(self) -> None:
        payload = _make_minimal_dicom_bytes()
        records = await _decode_bytes(DicomFormat(), payload)
        assert records[0]["modality"] == "CT"


# ---------------------------------------------------------------------------
# Decode — error paths
# ---------------------------------------------------------------------------

class TestDicomDecodeErrors:
    @pytest.mark.asyncio
    async def test_invalid_payload_type_raises_type_error(self) -> None:
        fmt = DicomFormat()

        async def _bad_iter():
            yield "not bytes"

        with pytest.raises((TypeError, Exception)):
            async for _ in await fmt.read(_bad_iter()):
                pass

    @pytest.mark.asyncio
    async def test_non_dicom_bytes_raises(self) -> None:
        fmt = DicomFormat()

        async def _iter():
            yield b"this is not a dicom file at all"

        with pytest.raises(Exception):
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Encode — error paths
# ---------------------------------------------------------------------------

class TestDicomEncodeErrors:
    @pytest.mark.asyncio
    async def test_encode_empty_raises_value_error(self) -> None:
        fmt = DicomFormat()

        async def _empty():
            return
            yield  # make it an async generator

        with pytest.raises(ValueError, match="empty"):
            async for _ in await fmt.write(_empty()):
                pass

    @pytest.mark.asyncio
    async def test_encode_invalid_pixel_data_type(self) -> None:
        fmt = DicomFormat()
        bad_record = {
            "sop_instance_uid": "",
            "study_uid": "",
            "series_uid": "",
            "modality": "OT",
            "pixel_data": "not bytes",
            "pixel_array_shape": (1, 1),
        }

        async def _records():
            yield bad_record

        with pytest.raises(TypeError):
            async for _ in await fmt.write(_records()):
                pass


# ---------------------------------------------------------------------------
# Round-trip (encode → decode)
# ---------------------------------------------------------------------------

class TestDicomRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        """Encode a minimal record and decode it back; check non-PHI fields."""
        import pydicom
        from pydicom.uid import generate_uid

        sop_uid = generate_uid()
        study_uid = generate_uid()
        series_uid = generate_uid()

        record = {
            "sop_instance_uid": sop_uid,
            "patient_id_hash": hashlib.sha256(b"").hexdigest(),
            "study_uid": study_uid,
            "series_uid": series_uid,
            "modality": "MR",
            "pixel_data": bytes([0, 128, 64, 32]),
            "pixel_array_shape": (2, 2),
            "metadata": {},
        }

        fmt = DicomFormat()
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)

        assert len(decoded) == 1
        assert decoded[0]["sop_instance_uid"] == sop_uid
        assert decoded[0]["modality"] == "MR"
        assert decoded[0]["pixel_data"] == bytes([0, 128, 64, 32])
        assert decoded[0]["pixel_array_shape"] == (2, 2)

    @pytest.mark.asyncio
    async def test_round_trip_phi_stripped_on_decode(self) -> None:
        """PatientName must not appear in decoded metadata even if encoded."""
        from pydicom.uid import generate_uid

        record = {
            "sop_instance_uid": generate_uid(),
            "patient_id_hash": hashlib.sha256(b"").hexdigest(),
            "study_uid": generate_uid(),
            "series_uid": generate_uid(),
            "modality": "OT",
            "pixel_data": b"\x00",
            "pixel_array_shape": (1, 1),
            "metadata": {},
        }

        fmt = DicomFormat()
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)

        assert "PatientName" not in decoded[0].get("metadata", {})
        assert "patient_id" not in decoded[0]


# ---------------------------------------------------------------------------
# Missing pydicom guard
# ---------------------------------------------------------------------------

class TestDicomMissingDependency:
    def test_load_pydicom_raises_on_missing(self) -> None:
        with patch.dict("sys.modules", {"pydicom": None}):
            with pytest.raises(ImportError, match="pirn\\[dicom\\]"):
                DicomFormat._load_pydicom()
