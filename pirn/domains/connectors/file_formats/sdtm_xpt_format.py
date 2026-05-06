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

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class SdtmXptFormat(BatchFileFormat):
    """Whole-file SDTM XPT encoder/decoder backed by ``pyreadstat``.

    No PHI is present in standard SDTM submissions (data is
    de-identified before submission to FDA). No PHI sanitisation is
    applied.
    """

    @property
    def name(self) -> str:
        return "sdtm_xpt"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        pyreadstat = self._load_pyreadstat()
        with tempfile.NamedTemporaryFile(suffix=".xpt", delete=False) as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        try:
            df, meta = pyreadstat.read_xport(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        column_labels: dict[str, str] = {}
        if hasattr(meta, "column_labels") and meta.column_labels:
            column_labels = dict(
                zip(meta.column_names, meta.column_labels, strict=False)
            )
        file_label: str = ""
        if hasattr(meta, "file_label") and meta.file_label:
            file_label = str(meta.file_label)

        records: list[dict[str, Any]] = []
        rows = df.to_dict(orient="records")
        for index, row in enumerate(rows):
            record: dict[str, Any] = {k: v for k, v in row.items()}
            if index == 0:
                record["_metadata"] = {
                    "column_labels": column_labels,
                    "file_label": file_label,
                }
            records.append(record)
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        pyreadstat = self._load_pyreadstat()
        materialised = [dict(r) for r in records]
        # Extract metadata from first record if present
        column_labels: dict[str, str] = {}
        file_label: str = ""
        if materialised and "_metadata" in materialised[0]:
            meta = materialised[0]["_metadata"]
            if isinstance(meta, dict):
                column_labels = meta.get("column_labels") or {}
                file_label = meta.get("file_label") or ""

        # Strip _metadata from all rows before writing
        clean_rows: list[dict[str, Any]] = []
        for row in materialised:
            clean = {k: v for k, v in row.items() if k != "_metadata"}
            clean_rows.append(clean)

        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "SdtmXptFormat requires pandas. Install with "
                "`pip install pirn[health]`."
            ) from exc

        df = pd.DataFrame(clean_rows)
        with tempfile.NamedTemporaryFile(
            suffix=".xpt", delete=False
        ) as tmp:
            tmp_path = tmp.name
        try:
            col_names = list(df.columns)
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

    @staticmethod
    def _load_pyreadstat() -> Any:
        try:
            import pyreadstat
        except ImportError as exc:
            raise ImportError(
                "SdtmXptFormat requires pyreadstat. Install with "
                "`pip install pirn[health]`."
            ) from exc
        return pyreadstat
