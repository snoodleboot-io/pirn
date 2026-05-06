"""``EdfFormat`` — European Data Format (EDF) batch encoder/decoder.

EDF is a standard biosignal format for EEG, ECG, EMG and similar
physiological recordings. The reference Python binding, ``pyedflib``,
requires a filesystem path; a :mod:`tempfile` round-trip bridges the
gap between in-memory bytes and the library API.

PHI safety
----------
EDF headers carry patient metadata in fixed-width ASCII fields.
``EdfFormat`` strips the following from decoded records and replaces
any corresponding header field with ``"[REDACTED]"`` on encode:

* ``patientname``
* ``patientcode``
* ``birthdate``
* ``admincode``

Each decoded record represents one signal channel::

    {
        "signal_index":  int,
        "label":         str,
        "sample_rate":   int,
        "n_samples":     int,
        "physical_min":  float,
        "physical_max":  float,
        "data":          bytes,  # raw float64 array bytes
    }

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class EdfFormat(BatchFileFormat):
    """Whole-file EDF encoder/decoder backed by ``pyedflib``.

    PHI fields (``patientname``, ``patientcode``, ``birthdate``,
    ``admincode``) are stripped from decoded records and redacted on
    encode.
    """

    _phi_header_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "patientname",
            "patientcode",
            "birthdate",
            "admincode",
        }
    )

    # File extension passed to tempfile so pyedflib recognises the format.
    _file_suffix: ClassVar[str] = ".edf"

    @property
    def name(self) -> str:
        return "edf"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        pyedflib = self._load_pyedflib()
        with tempfile.NamedTemporaryFile(suffix=self._file_suffix, delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(payload)
        try:
            records = self._read_signals(pyedflib, tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return records

    @classmethod
    def _read_signals(cls, pyedflib: Any, path: str) -> list[Mapping[str, Any]]:
        import numpy as np

        records: list[Mapping[str, Any]] = []
        with pyedflib.EdfReader(path) as reader:
            n_signals = reader.signals_in_file
            for idx in range(n_signals):
                signal = reader.readSignal(idx)
                record: dict[str, Any] = {
                    "signal_index": idx,
                    "label": reader.getLabel(idx).strip(),
                    "sample_rate": int(reader.getSampleFrequency(idx)),
                    "n_samples": int(reader.getNSamples()[idx]),
                    "physical_min": float(reader.getPhysicalMinimum(idx)),
                    "physical_max": float(reader.getPhysicalMaximum(idx)),
                    "data": signal.astype(np.float64).tobytes(),
                }
                records.append(record)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        import numpy as np

        pyedflib = self._load_pyedflib()
        materialised = [dict(r) for r in records]
        # Separate annotation record (EDF+) from signal records
        signal_records, annotation_record = self._split_records(materialised)

        if not signal_records:
            raise ValueError(
                f"{type(self).__name__}: cannot encode empty signal stream — "
                "at least one signal channel record is required."
            )

        with tempfile.NamedTemporaryFile(suffix=self._file_suffix, delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pyedflib.EdfWriter(tmp_path, len(signal_records)) as writer:
                self._apply_phi_redaction(writer)
                headers = []
                signal_arrays = []
                for rec in signal_records:
                    data_bytes = rec.get("data", b"")
                    arr = np.frombuffer(data_bytes, dtype=np.float64)
                    n_samples = int(rec.get("n_samples", len(arr)))
                    sample_rate = int(rec.get("sample_rate", 1))
                    phys_min = float(rec.get("physical_min", -32768.0))
                    phys_max = float(rec.get("physical_max", 32767.0))
                    label = str(rec.get("label", ""))
                    headers.append(
                        {
                            "label": label,
                            "dimension": "",
                            "sample_frequency": sample_rate,
                            "physical_min": phys_min,
                            "physical_max": phys_max,
                            "digital_min": -32768,
                            "digital_max": 32767,
                            "transducer": "",
                            "prefilter": "",
                        }
                    )
                    # Ensure array length matches n_samples
                    if len(arr) < n_samples:
                        arr = np.pad(arr, (0, n_samples - len(arr)))
                    elif len(arr) > n_samples:
                        arr = arr[:n_samples]
                    signal_arrays.append(arr)

                writer.setSignalHeaders(headers)
                self._write_annotations(writer, annotation_record)
                writer.writeSamples(signal_arrays)
            payload = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return payload

    @staticmethod
    def _split_records(
        records: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        signal_records = []
        annotation_record = None
        for rec in records:
            if "_edfplus_annotations" in rec:
                annotation_record = rec
            else:
                signal_records.append(rec)
        return signal_records, annotation_record

    @staticmethod
    def _apply_phi_redaction(writer: Any) -> None:
        """Set patient/admin fields to [REDACTED] in the EDF header."""
        import warnings

        _setters = [
            ("setPatientCode", "[REDACTED]"),
            ("setPatientName", "[REDACTED]"),
            ("setBirthDate", ""),
            ("setAdmincode", "[REDACTED]"),
        ]
        applied = 0
        for method_name, value in _setters:
            try:
                getattr(writer, method_name)(value)
                applied += 1
            except AttributeError:
                warnings.warn(
                    f"EdfFormat: pyedflib writer does not expose {method_name!r}; "
                    "PHI field not redacted. Upgrade pyedflib or do not call encode "
                    "with PHI-bearing records.",
                    RuntimeWarning,
                    stacklevel=4,
                )
        if applied == 0:
            raise RuntimeError(
                "EdfFormat: none of the PHI-redaction setters are available on "
                "this pyedflib version. Cannot safely encode records — install a "
                "supported pyedflib version (>=1.0)."
            )

    @staticmethod
    def _write_annotations(writer: Any, annotation_record: dict[str, Any] | None) -> None:
        """Write EDF+ annotations if present. No-op for plain EDF."""
        pass  # Overridden in EdfPlusFormat

    @staticmethod
    def _load_pyedflib() -> Any:
        try:
            import pyedflib
        except ImportError as exc:
            raise ImportError(
                "EdfFormat requires pyedflib. Install with `pip install pirn[health]`."
            ) from exc
        return pyedflib
