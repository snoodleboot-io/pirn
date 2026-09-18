"""Unit tests for :class:`DicomObjectStoreDisassembler`."""

from __future__ import annotations

import unittest

try:
    import pydicom
except ImportError as _e:
    raise unittest.SkipTest("pydicom not installed") from _e

from pirn.core.knot_config import KnotConfig
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from pirn_health.disassemblers.dicom_object_store_disassembler import (
    DicomObjectStoreDisassembler,
)
from pirn_health.types.dicom_payload import DICOMPayload
from pirn_health.types.dicom_series import DICOMSeries

_CFG = KnotConfig(id="d")


def _sample_dataset() -> pydicom.Dataset:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset("in-memory.dcm", {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.PatientID = "P123"
    return ds


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DicomObjectStoreDisassembler:
        payload = DICOMPayload(metadata=DICOMSeries(), data=_sample_dataset())
        return DicomObjectStoreDisassembler(payload=payload, _config=_CFG)

    async def test_rejects_non_payload(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DICOMPayload"):
            await knot.process(payload="not-a-payload")

    async def test_rejects_dataset_without_save_as(self) -> None:
        knot = self._make_knot()
        bad_payload = DICOMPayload(metadata=DICOMSeries(), data="not-a-dataset")
        with self.assertRaisesRegex(TypeError, "save_as"):
            await knot.process(payload=bad_payload)

    async def test_serialises_dataset_to_bytes_no_disk_io(self) -> None:
        knot = self._make_knot()
        dataset = _sample_dataset()
        payload = DICOMPayload(metadata=DICOMSeries(), data=dataset)
        out = await knot.process(payload=payload)
        assert isinstance(out, bytes)
        round_tripped = pydicom.dcmread(pydicom.filebase.DicomBytesIO(out))
        assert round_tripped.PatientID == "P123"
