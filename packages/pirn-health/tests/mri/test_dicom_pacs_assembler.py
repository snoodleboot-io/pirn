"""Unit tests for :class:`DicomPacsAssembler`."""

from __future__ import annotations

import unittest

try:
    import pydicom
except ImportError as _e:
    raise unittest.SkipTest("pydicom not installed") from _e

import io

from pirn.core.knot_config import KnotConfig
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from pirn_health.assemblers.dicom_pacs_assembler import DicomPacsAssembler
from pirn_health.types.dicom_payload import DICOMPayload

_CFG = KnotConfig(id="a")


def _sample_dicom_bytes() -> bytes:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset("in-memory.dcm", {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.PatientID = "P123"
    ds.SeriesInstanceUID = "1.2.3.4.5.6"
    buf = io.BytesIO()
    ds.save_as(buf)
    return buf.getvalue()


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DicomPacsAssembler:
        return DicomPacsAssembler(body=b"", series_id="s1", _config=_CFG)

    async def test_rejects_non_bytes_body(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "body"):
            await knot.process(body="not-bytes", series_id="s1")  # type: ignore[arg-type]

    async def test_rejects_non_string_series_id(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "series_id"):
            await knot.process(body=b"x", series_id=42)  # type: ignore[arg-type]

    async def test_rejects_empty_series_id(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(body=b"x", series_id="")

    async def test_parses_bytes_into_dataset_no_disk_io(self) -> None:
        knot = self._make_knot()
        body = _sample_dicom_bytes()
        payload = await knot.process(body=body, series_id="s1")
        assert isinstance(payload, DICOMPayload)
        assert isinstance(payload.data, pydicom.Dataset)
        assert payload.data.PatientID == "P123"
        assert payload.metadata.series_uid == "s1"
