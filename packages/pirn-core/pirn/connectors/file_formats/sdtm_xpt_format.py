"""``SdtmXptFormat`` — SDTM SAS Transport (XPT) batch encoder/decoder.

SDTM XPT is the SAS Transport format mandated by FDA for clinical trial
data submissions. ``pyreadstat`` provides read/write support.

One record is emitted per row. The **first** record additionally contains
a ``_metadata`` key with::

    {
        "_metadata": {
            "column_labels": {col_name: label, ...},
            "file_label":    str,
        }
    }

Install: ``pip install "pirn-core[spss]"`` (``pyreadstat``) and
``pip install "pirn-data[data]"`` (``pandas``, for writing).
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.payload_shape import PayloadShape
from pirn.core.optional_dependency import OptionalDependency


class SdtmXptFormat(BatchFileFormat):
    """Whole-file SDTM XPT encoder/decoder backed by ``pyreadstat``.

    No PHI is present in standard SDTM submissions (data is
    de-identified before submission to FDA). No PHI sanitisation is
    applied.

    One record is emitted per data row. Column values use their native
    Python types as returned by ``pyreadstat``. The first record
    additionally carries a ``_metadata`` key::

        # First record only:
        {
            "<col1>": <value>,
            "<col2>": <value>,
            ...
            "_metadata": {
                "column_labels":  dict[str, str],  # column name → label
                "file_label":     str,
            },
        }

        # Subsequent records:
        {
            "<col1>": <value>,
            "<col2>": <value>,
            ...
        }
    """

    @property
    def name(self) -> str:
        return "sdtm_xpt"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        pyreadstat = OptionalDependency.require("pyreadstat", extra="spss")
        with tempfile.NamedTemporaryFile(suffix=".xpt", delete=False) as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        try:
            df, meta = pyreadstat.read_xport(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        column_labels: dict[str, str] = {}
        if hasattr(meta, "column_labels") and meta.column_labels:
            column_labels = dict(zip(meta.column_names, meta.column_labels, strict=False))
        file_label: str = ""
        if hasattr(meta, "file_label") and meta.file_label:
            file_label = str(meta.file_label)

        records: list[dict[str, Any]] = []
        rows: list[Mapping[str, Any]] = df.to_dict(orient="records")
        for index, row in enumerate(rows):
            record: dict[str, Any] = dict(row)
            if index == 0:
                record["_metadata"] = {
                    "column_labels": column_labels,
                    "file_label": file_label,
                }
            records.append(record)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        pyreadstat = OptionalDependency.require("pyreadstat", extra="spss")
        materialised = [dict(r) for r in records]
        # Extract metadata from first record if present
        column_labels: dict[str, str] = {}
        file_label: str = ""
        if materialised and "_metadata" in materialised[0]:
            meta: object = materialised[0]["_metadata"]
            if PayloadShape.is_str_dict(meta):
                labels_value = meta.get("column_labels")
                if PayloadShape.is_mapping(labels_value):
                    column_labels = {str(name): str(label) for name, label in labels_value.items()}
                label_value = meta.get("file_label")
                file_label = str(label_value) if label_value else ""

        # Strip _metadata from all rows before writing
        clean_rows: list[dict[str, Any]] = []
        for row in materialised:
            clean = {k: v for k, v in row.items() if k != "_metadata"}
            clean_rows.append(clean)

        pd = OptionalDependency.require("pandas", extra="data", package="pirn-data")
        df = pd.DataFrame(clean_rows)
        with tempfile.NamedTemporaryFile(suffix=".xpt", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            col_names: list[str] = [str(c) for c in df.columns]
            labels = [column_labels.get(c, "") for c in col_names]
            pyreadstat.write_xport(
                df,
                tmp_path,
                file_label=file_label,
                column_labels=labels,
            )
            return Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
