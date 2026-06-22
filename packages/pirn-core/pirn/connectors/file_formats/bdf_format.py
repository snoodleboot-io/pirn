"""``BdfFormat`` — BioSemi Data Format (BDF) batch encoder/decoder.

BDF is a 24-bit variant of EDF primarily used for high-density EEG
recordings from BioSemi ActiveTwo amplifiers. The ``pyedflib`` library
handles both formats; BDF files use the ``.bdf`` extension and 24-bit
(``bits_per_record=24``) encoding.

PHI safety
----------
Identical to :class:`EdfFormat`: ``patientname``, ``patientcode``,
``birthdate``, and ``admincode`` are stripped from decoded records and
replaced with ``"[REDACTED]"`` on encode.

Record shape (one per signal channel)::

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

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class BdfFormat(BatchFileFormat):
    """Whole-file BDF encoder/decoder backed by ``pyedflib``.

    BDF is a 24-bit extension of EDF; this class mirrors EdfFormat
    but uses the ``.bdf`` file extension so pyedflib selects the
    correct bit-depth.

    One record is emitted per signal channel::

        {
            "signal_index":  int,
            "label":         str,
            "sample_rate":   int,
            "n_samples":     int,
            "physical_min":  float,
            "physical_max":  float,
            "data":          bytes,  # raw float64 array bytes
        }
    """

    _phi_header_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "patientname",
            "patientcode",
            "birthdate",
            "admincode",
        }
    )

    @property
    def name(self) -> str:
        return "bdf"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        import numpy as np

        pyedflib = self._load_pyedflib()
        with tempfile.NamedTemporaryFile(suffix=".bdf", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(payload)
        try:
            records: list[Mapping[str, Any]] = []
            with pyedflib.EdfReader(tmp_path) as reader:
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
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        import numpy as np

        pyedflib = self._load_pyedflib()
        materialised = [dict(r) for r in records]
        if not materialised:
            raise ValueError(
                "BdfFormat: cannot encode empty signal stream — "
                "at least one signal channel record is required."
            )

        with tempfile.NamedTemporaryFile(suffix=".bdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # filetype=2 selects EDF+/BDF+ in pyedflib (BDF = type 3 in
            # some versions). Try filetype keyword; fall back to default.
            with pyedflib.EdfWriter(
                tmp_path, len(materialised), file_type=pyedflib.FILETYPE_BDF
            ) as writer:
                self._apply_phi_redaction(writer)
                headers = []
                signal_arrays = []
                for i, rec in enumerate(materialised):
                    for field in ("data", "sample_rate"):
                        if field not in rec:
                            raise KeyError(
                                f"BdfFormat: signal record[{i}] missing required field "
                                f"'{field}'; got: {list(rec)}"
                            )
                    data_bytes = rec["data"]
                    arr = np.frombuffer(data_bytes, dtype=np.float64)
                    n_samples = int(rec.get("n_samples", len(arr)))
                    sample_rate = int(rec["sample_rate"])
                    phys_min = float(rec.get("physical_min", -8000000.0))
                    phys_max = float(rec.get("physical_max", 8000000.0))
                    label = str(rec.get("label", ""))
                    headers.append(
                        {
                            "label": label,
                            "dimension": "uV",
                            "sample_frequency": sample_rate,
                            "physical_min": phys_min,
                            "physical_max": phys_max,
                            "digital_min": -8388608,
                            "digital_max": 8388607,
                            "transducer": "",
                            "prefilter": "",
                        }
                    )
                    if len(arr) < n_samples:
                        arr = np.pad(arr, (0, n_samples - len(arr)))
                    elif len(arr) > n_samples:
                        arr = arr[:n_samples]
                    signal_arrays.append(arr)

                writer.setSignalHeaders(headers)
                writer.writeSamples(signal_arrays)
            payload = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return payload

    @staticmethod
    def _apply_phi_redaction(writer: Any) -> None:
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
                    f"BdfFormat: pyedflib writer does not expose {method_name!r}; "
                    "PHI field not redacted. Upgrade pyedflib or do not call encode "
                    "with PHI-bearing records.",
                    RuntimeWarning,
                    stacklevel=4,
                )
        if applied == 0:
            raise RuntimeError(
                "BdfFormat: none of the PHI-redaction setters are available on "
                "this pyedflib version. Cannot safely encode records — install a "
                "supported pyedflib version (>=1.0)."
            )

    @staticmethod
    def _load_pyedflib() -> Any:
        try:
            import pyedflib
        except ImportError as exc:
            raise ImportError(
                "BdfFormat requires pyedflib. Install with `pip install pirn[health]`."
            ) from exc
        return pyedflib
