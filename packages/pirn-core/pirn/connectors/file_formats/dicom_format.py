"""``DicomFormat`` — DICOM (medical imaging) batch encoder/decoder.

DICOM (Digital Imaging and Communications in Medicine) is the de-facto
container for radiology, ultrasound, CT, MRI and other modality output.
The reference Python binding, ``pydicom``, expects either a filesystem
path or an :class:`io.BytesIO`. The whole payload must be buffered
before decoding, so this is a :class:`BatchFileFormat`.

PHI safety
----------
DICOM datasets routinely carry Protected Health Information (PHI):
patient name, birth date, address, etc. ``DicomFormat`` REFUSES to
emit raw PHI. The decode path:

* Hashes ``PatientID`` with SHA-256 and emits the hex digest as
  ``patient_id_hash`` — never the raw value.
* DROPS ``PatientName``, ``PatientBirthDate``, ``PatientAddress``
  (and known synonyms) from the ``metadata`` mapping. Callers who
  need re-identifiable data must operate against the source DICOM
  bytes directly with explicit access controls; this format is the
  audited surface and treats the carve-out as load-bearing.

Records are emitted as ONE record per file with shape::

    {
        "sop_instance_uid":   str,
        "patient_id_hash":    str,    # SHA-256 hex digest of PatientID
        "study_uid":          str,
        "series_uid":         str,
        "modality":           str,
        "pixel_array_shape":  tuple,
        "pixel_data":         bytes,  # raw PixelData
        "metadata":           Mapping (sanitised),
    }

Install: ``pip install "pirn-health[health]"``.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, ClassVar, SupportsIndex, SupportsInt

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.payload_shape import PayloadShape
from pirn.core.optional_dependency import OptionalDependency


class DicomFormat(BatchFileFormat):
    """Whole-file DICOM encoder/decoder backed by ``pydicom``.

    PHI fields (``PatientName``, ``PatientBirthDate``, ``PatientAddress``
    and known synonyms) are stripped from the emitted ``metadata``
    mapping. ``PatientID`` is hashed with SHA-256 before emission.

    One record is emitted per file::

        {
            "sop_instance_uid":   str,
            "patient_id_hash":    str,    # SHA-256 hex digest of PatientID
            "study_uid":          str,
            "series_uid":         str,
            "modality":           str,
            "pixel_array_shape":  tuple,
            "pixel_data":         bytes,  # raw PixelData bytes
            "metadata":           Mapping,  # sanitised non-PHI DICOM tags
        }
    """

    # Keywords that are forbidden from appearing in the emitted metadata
    # mapping. These map to PHI under HIPAA; emitting them through the
    # audited record surface would defeat the purpose of the carve-out.
    _phi_keywords: ClassVar[frozenset[str]] = frozenset(
        {
            # Direct identifiers
            "PatientName",
            "PatientBirthDate",
            "PatientAddress",
            "PatientTelephoneNumbers",
            "PatientMotherBirthName",
            "PatientBirthName",
            "OtherPatientNames",
            "OtherPatientIDs",
            "ResponsiblePerson",
            "ResponsiblePersonRole",
            "ResponsibleOrganization",
            "PatientID",  # raw — emitted separately as patient_id_hash
            "IssuerOfPatientID",
            # Free-text fields routinely containing PHI
            "PatientComments",
            "AdditionalPatientHistory",
            "MedicalAlerts",
            "Allergies",
            "SmokingStatus",
            # HIPAA Safe Harbor quasi-identifiers (categories 3, 9, 10, 16)
            "EthnicGroup",
            "Occupation",
            "PatientAge",
            "PatientWeight",
            "PatientSize",
            "PatientBodyMassIndex",
        }
    )

    @property
    def name(self) -> str:
        return "dicom"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"DicomFormat: payload must be bytes, got {type(payload).__name__}")
        pydicom = OptionalDependency.require("pydicom", extra="health", package="pirn-health")
        dataset = pydicom.dcmread(io.BytesIO(bytes(payload)))
        patient_id = self._safe_text(getattr(dataset, "PatientID", ""))
        record: dict[str, Any] = {
            "sop_instance_uid": self._safe_text(getattr(dataset, "SOPInstanceUID", "")),
            "patient_id_hash": self._hash_patient_id(patient_id),
            "study_uid": self._safe_text(getattr(dataset, "StudyInstanceUID", "")),
            "series_uid": self._safe_text(getattr(dataset, "SeriesInstanceUID", "")),
            "modality": self._safe_text(getattr(dataset, "Modality", "")),
            "pixel_array_shape": self._extract_pixel_shape(dataset),
            "pixel_data": self._extract_pixel_bytes(dataset),
            "metadata": self._sanitise_metadata(dataset),
        }
        return [record]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        materialised = [dict(record) for record in records]
        if not materialised:
            raise ValueError(
                "DicomFormat: cannot encode an empty record stream — "
                "DICOM requires exactly one dataset per file."
            )
        record = materialised[0]
        pydicom = OptionalDependency.require("pydicom", extra="health", package="pirn-health")
        dataset = self._build_dataset(record)
        buf = io.BytesIO()
        # ``write_like_original=False`` writes the DICOM File Meta
        # Information preamble so the bytes are a valid Part-10 file
        # round-trippable through ``dcmread``. Newer pydicom releases
        # renamed the kwarg to ``enforce_file_format`` — try both.
        self._dcmwrite(pydicom, dataset, buf)
        return buf.getvalue()

    @classmethod
    def _build_dataset(cls, record: Mapping[str, Any]) -> Any:
        pydicom_dataset = OptionalDependency.require(
            "pydicom.dataset", extra="health", package="pirn-health"
        )
        pydicom_uid = OptionalDependency.require(
            "pydicom.uid", extra="health", package="pirn-health"
        )
        generate_uid = pydicom_uid.generate_uid

        file_meta = pydicom_dataset.FileMetaDataset()
        sop_instance = cls._safe_text(record.get("sop_instance_uid", ""))
        if not sop_instance:
            sop_instance = generate_uid()
        # SecondaryCaptureImageStorage — generic SOP class for round-trip
        # tests where no specific modality storage class is required.
        file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
        file_meta.MediaStorageSOPInstanceUID = sop_instance
        file_meta.TransferSyntaxUID = pydicom_uid.ExplicitVRLittleEndian

        dataset = pydicom_dataset.Dataset()
        dataset.file_meta = file_meta
        dataset.is_little_endian = True
        dataset.is_implicit_VR = False
        dataset.SOPInstanceUID = sop_instance
        dataset.SOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
        dataset.StudyInstanceUID = cls._safe_text(record.get("study_uid", "")) or generate_uid()
        dataset.SeriesInstanceUID = cls._safe_text(record.get("series_uid", "")) or generate_uid()
        if "modality" not in record:
            raise KeyError(
                f"DicomFormat: record missing required field 'modality'; got: {list(record)}"
            )
        dataset.Modality = cls._safe_text(record["modality"])

        pixel_data = record.get("pixel_data", b"")
        if not isinstance(pixel_data, (bytes, bytearray)):
            raise TypeError(
                f"DicomFormat: 'pixel_data' must be bytes, got {type(pixel_data).__name__}"
            )
        shape = record.get("pixel_array_shape")
        rows, columns = cls._coerce_shape(shape)
        dataset.Rows = rows
        dataset.Columns = columns
        dataset.SamplesPerPixel = 1
        dataset.PhotometricInterpretation = "MONOCHROME2"
        dataset.BitsAllocated = 8
        dataset.BitsStored = 8
        dataset.HighBit = 7
        dataset.PixelRepresentation = 0
        dataset.PixelData = bytes(pixel_data)
        return dataset

    @staticmethod
    def _dcmwrite(pydicom: Any, dataset: Any, buf: io.BytesIO) -> None:
        # pydicom>=3 renamed ``write_like_original`` to
        # ``enforce_file_format`` (inverted semantics).
        try:
            pydicom.dcmwrite(buf, dataset, enforce_file_format=True)
            return
        except TypeError:
            pass
        pydicom.dcmwrite(buf, dataset, write_like_original=False)

    @classmethod
    def _coerce_shape(cls, shape: object) -> tuple[int, int]:
        if shape is None:
            return 1, 1
        dims: Sequence[object] = shape if PayloadShape.is_sequence(shape) else ()
        if len(dims) >= 2:
            rows = cls._coerce_dim(dims[0])
            columns = cls._coerce_dim(dims[1])
            if rows <= 0 or columns <= 0:
                raise ValueError(
                    f"DicomFormat: pixel_array_shape rows/columns must be positive, got {shape!r}"
                )
            return rows, columns
        raise ValueError(
            f"DicomFormat: pixel_array_shape must be a (rows, cols[, ...]) tuple, got {shape!r}"
        )

    @staticmethod
    def _coerce_dim(value: object) -> int:
        if isinstance(value, (str, bytes, bytearray, SupportsInt, SupportsIndex)):
            return int(value)
        raise TypeError(
            f"DicomFormat: pixel_array_shape entries must be integers, got {type(value).__name__}"
        )

    @classmethod
    def _sanitise_metadata(cls, dataset: Any) -> Mapping[str, Any]:
        sanitised: dict[str, Any] = {}
        for element in dataset.iterall():
            keyword = element.keyword
            if not keyword:
                continue
            if keyword in cls._phi_keywords:
                continue
            value = element.value
            sanitised[keyword] = cls._coerce_metadata_value(value)
        # Strip pixel data from metadata — emitted separately as raw
        # bytes via ``pixel_data``.
        sanitised.pop("PixelData", None)
        return sanitised

    @staticmethod
    def _coerce_metadata_value(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, bytes):
            # Avoid emitting raw bytes through the audit dict.
            return f"<{len(value)} bytes>"
        # Multi-value DICOM elements expose ``__iter__``; coerce to
        # tuple of stringified values so the dict is JSON-friendly.
        try:
            return tuple(str(item) for item in value)
        except TypeError:
            return str(value)

    @staticmethod
    def _hash_patient_id(patient_id: str) -> str:
        digest = hashlib.sha256(patient_id.encode("utf-8")).hexdigest()
        return digest

    @staticmethod
    def _safe_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _extract_pixel_shape(dataset: Any) -> tuple[int, ...]:
        if not hasattr(dataset, "PixelData"):
            return ()
        try:
            array = dataset.pixel_array
        except (AttributeError, KeyError, ValueError, TypeError):
            rows = int(getattr(dataset, "Rows", 0) or 0)
            columns = int(getattr(dataset, "Columns", 0) or 0)
            return (rows, columns) if rows and columns else ()
        return tuple(int(dim) for dim in array.shape)

    @staticmethod
    def _extract_pixel_bytes(dataset: Any) -> bytes:
        pixel_data = getattr(dataset, "PixelData", b"")
        if pixel_data is None:
            return b""
        if isinstance(pixel_data, (bytes, bytearray)):
            return bytes(pixel_data)
        return bytes(pixel_data)
