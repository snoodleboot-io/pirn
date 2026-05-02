"""``MzmlFormat`` — mzML mass spectrometry batch encoder/decoder.

mzML is an XML-based open standard for mass spectrometry data used in
proteomics and metabolomics. ``pyteomics`` provides an efficient mzML
reader; ``lxml`` is used for writing.

Records are emitted as ONE record per spectrum::

    {
        "scan_number":       int,
        "ms_level":          int,
        "retention_time":    float,   # seconds
        "mz_array":          bytes,   # raw float64 little-endian bytes
        "intensity_array":   bytes,   # raw float64 little-endian bytes
    }

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import base64
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class MzmlFormat(BatchFileFormat):
    """Whole-file mzML encoder/decoder backed by ``pyteomics``."""

    @property
    def name(self) -> str:
        return "mzml"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        import io as _io

        pyteomics_mzml = self._load_pyteomics_mzml()
        records: list[Mapping[str, Any]] = []
        with pyteomics_mzml.MzML(_io.BytesIO(payload)) as reader:
            for spectrum in reader:
                records.append(self._spectrum_to_record(spectrum))
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        lxml_etree = self._load_lxml()
        import io as _io
        import numpy as np

        materialised = list(records)
        nsmap = {None: "http://psi.hupo.org/ms/mzml"}
        root = lxml_etree.Element("mzML", nsmap=nsmap)
        run_el = lxml_etree.SubElement(root, "run")
        spec_list = lxml_etree.SubElement(
            run_el, "spectrumList", count=str(len(materialised))
        )
        for index, record in enumerate(materialised):
            self._record_to_spectrum_element(
                spec_list, record, index, lxml_etree, np
            )
        buf = _io.BytesIO()
        tree = lxml_etree.ElementTree(root)
        tree.write(
            buf,
            xml_declaration=True,
            encoding="utf-8",
            pretty_print=True,
        )
        return buf.getvalue()

    @staticmethod
    def _spectrum_to_record(spectrum: Any) -> dict[str, Any]:
        import numpy as np

        scan_number = 0
        scan_info = spectrum.get("scanList", {}).get("scan", [{}])
        if scan_info:
            scan_number = int(
                scan_info[0].get("scan start time", 0) * 1000
            )
        # pyteomics uses 'id' field for the spectrum identifier
        spec_id = spectrum.get("id", "")
        if "scan=" in str(spec_id):
            try:
                scan_number = int(str(spec_id).split("scan=")[-1])
            except ValueError:
                pass

        ms_level = int(spectrum.get("ms level", 1))
        retention_time = 0.0
        if scan_info:
            rt_raw = scan_info[0].get("scan start time", 0.0)
            rt_unit = scan_info[0].get(
                "scan start time", {}
            )
            retention_time = float(rt_raw) if rt_raw else 0.0

        mz = spectrum.get("m/z array")
        intensity = spectrum.get("intensity array")
        mz_bytes = (
            np.asarray(mz, dtype=np.float64).tobytes()
            if mz is not None
            else b""
        )
        intensity_bytes = (
            np.asarray(intensity, dtype=np.float64).tobytes()
            if intensity is not None
            else b""
        )
        return {
            "scan_number": scan_number,
            "ms_level": ms_level,
            "retention_time": retention_time,
            "mz_array": mz_bytes,
            "intensity_array": intensity_bytes,
        }

    @staticmethod
    def _record_to_spectrum_element(
        parent: Any,
        record: Mapping[str, Any],
        index: int,
        etree: Any,
        np: Any,
    ) -> None:
        scan_number = record.get("scan_number", index + 1)
        ms_level = record.get("ms_level", 1)
        retention_time = record.get("retention_time", 0.0)
        mz_raw = record.get("mz_array", b"")
        intensity_raw = record.get("intensity_array", b"")
        if not isinstance(mz_raw, (bytes, bytearray)):
            raise TypeError(
                "MzmlFormat: 'mz_array' must be bytes, got "
                f"{type(mz_raw).__name__}"
            )
        if not isinstance(intensity_raw, (bytes, bytearray)):
            raise TypeError(
                "MzmlFormat: 'intensity_array' must be bytes, got "
                f"{type(intensity_raw).__name__}"
            )
        mz_arr = np.frombuffer(mz_raw, dtype=np.float64)
        intensity_arr = np.frombuffer(intensity_raw, dtype=np.float64)

        spec_el = etree.SubElement(
            parent,
            "spectrum",
            index=str(index),
            id=f"scan={scan_number}",
            defaultArrayLength=str(len(mz_arr)),
        )
        # cvParam elements for ms level and retention time
        etree.SubElement(
            spec_el,
            "cvParam",
            accession="MS:1000511",
            name="ms level",
            value=str(ms_level),
        )
        scan_list = etree.SubElement(spec_el, "scanList", count="1")
        scan_el = etree.SubElement(scan_list, "scan")
        etree.SubElement(
            scan_el,
            "cvParam",
            accession="MS:1000016",
            name="scan start time",
            value=str(retention_time),
            unitName="second",
        )
        binary_array_list = etree.SubElement(
            spec_el, "binaryDataArrayList", count="2"
        )

        for arr, accession, array_name in (
            (mz_arr, "MS:1000514", "m/z array"),
            (intensity_arr, "MS:1000515", "intensity array"),
        ):
            bda = etree.SubElement(binary_array_list, "binaryDataArray")
            etree.SubElement(
                bda,
                "cvParam",
                accession="MS:1000514",
                name=array_name,
            )
            etree.SubElement(
                bda,
                "cvParam",
                accession="MS:1000576",
                name="no compression",
            )
            etree.SubElement(
                bda,
                "cvParam",
                accession="MS:1000514",
                name="64-bit float",
            )
            binary_el = etree.SubElement(bda, "binary")
            binary_el.text = base64.b64encode(
                arr.astype(np.float64).tobytes()
            ).decode("ascii")

    @staticmethod
    def _load_pyteomics_mzml() -> Any:
        try:
            from pyteomics import mzml
        except ImportError as exc:
            raise ImportError(
                "MzmlFormat requires pyteomics. Install with "
                "`pip install pirn[health]`."
            ) from exc
        return mzml

    @staticmethod
    def _load_lxml() -> Any:
        try:
            from lxml import etree
        except ImportError as exc:
            raise ImportError(
                "MzmlFormat requires lxml. Install with "
                "`pip install pirn[health]`."
            ) from exc
        return etree
