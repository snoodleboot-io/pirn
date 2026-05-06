"""``OdsFormat`` — OpenDocument Spreadsheet (``.ods``) encoder/decoder.

Built directly on ``odfpy``: ``OpenDocumentSpreadsheet``, ``Table``,
``TableRow``, ``TableCell`` for writes; the same elements for reads,
walked via ``getElementsByType``.

ODS is a zipped XML bundle (similar shape to XLSX); random access
requires the whole archive, so this is a :class:`BatchFileFormat`.

Install: ``pip install pirn[ods]``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class OdsFormat(BatchFileFormat):
    """Whole-file ODS encoder/decoder backed by ``odfpy``."""

    def __init__(
        self,
        sheet_name: str = "Sheet1",
        has_header: bool = True,
    ) -> None:
        if not isinstance(sheet_name, str) or not sheet_name:
            raise ValueError("OdsFormat: sheet_name must be a non-empty string")
        if not isinstance(has_header, bool):
            raise TypeError(
                f"OdsFormat: has_header must be a bool, got {type(has_header).__name__}"
            )
        self._sheet_name = sheet_name
        self._has_header = has_header

    @property
    def name(self) -> str:
        return "ods"

    @property
    def sheet_name(self) -> str:
        return self._sheet_name

    @property
    def has_header(self) -> bool:
        return self._has_header

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        opendocument, table_ns, text_ns = self._load_odfpy_read()
        document = opendocument.load(io.BytesIO(payload))
        target_table = None
        for table in document.spreadsheet.getElementsByType(table_ns.Table):
            name_attr = table.getAttribute("name")
            if name_attr == self._sheet_name:
                target_table = table
                break
        if target_table is None:
            raise ValueError(f"OdsFormat: sheet {self._sheet_name!r} not found in document")
        rows: list[list[Any]] = []
        for row in target_table.getElementsByType(table_ns.TableRow):
            cells: list[Any] = []
            for cell in row.getElementsByType(table_ns.TableCell):
                repeat_raw = cell.getAttribute("numbercolumnsrepeated")
                try:
                    repeat = int(repeat_raw) if repeat_raw else 1
                except (TypeError, ValueError):
                    repeat = 1
                value = self._extract_cell_value(cell, text_ns)
                for _ in range(repeat):
                    cells.append(value)
            while cells and cells[-1] is None:
                cells.pop()
            if cells:
                rows.append(cells)
        if not rows:
            return []
        if self._has_header:
            header = [str(cell) if cell is not None else "" for cell in rows[0]]
            data_rows = rows[1:]
        else:
            header = [f"col_{index}" for index in range(len(rows[0]))]
            data_rows = rows
        records: list[Mapping[str, Any]] = []
        for row_values in data_rows:
            record: dict[str, Any] = {}
            for index, column in enumerate(header):
                record[column] = row_values[index] if index < len(row_values) else None
            records.append(record)
        return records

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        (
            opendocument_spreadsheet,
            table_ns,
            text_ns,
        ) = self._load_odfpy_write()
        materialised: list[Mapping[str, Any]] = list(records)
        document = opendocument_spreadsheet()
        table = table_ns.Table(name=self._sheet_name)
        columns: tuple[str, ...] = tuple(materialised[0].keys()) if materialised else ()
        if self._has_header and columns:
            header_row = table_ns.TableRow()
            for column in columns:
                cell = self._build_cell(column, table_ns, text_ns)
                header_row.addElement(cell)
            table.addElement(header_row)
        for record in materialised:
            data_row = table_ns.TableRow()
            for column in columns:
                cell = self._build_cell(record.get(column), table_ns, text_ns)
                data_row.addElement(cell)
            table.addElement(data_row)
        document.spreadsheet.addElement(table)
        buf = io.BytesIO()
        document.write(buf)
        return buf.getvalue()

    @classmethod
    def _build_cell(cls, value: Any, table_ns: Any, text_ns: Any) -> Any:
        if value is None:
            return table_ns.TableCell()
        if isinstance(value, bool):
            cell = table_ns.TableCell(
                valuetype="boolean",
                booleanvalue="true" if value else "false",
            )
            cell.addElement(text_ns.P(text=str(value).lower()))
            return cell
        if isinstance(value, (int, float)):
            cell = table_ns.TableCell(
                valuetype="float",
                value=str(value),
            )
            cell.addElement(text_ns.P(text=str(value)))
            return cell
        text_value = str(value)
        cell = table_ns.TableCell(valuetype="string")
        cell.addElement(text_ns.P(text=text_value))
        return cell

    @staticmethod
    def _extract_cell_value(cell: Any, text_ns: Any) -> Any:
        value_type = cell.getAttribute("valuetype")
        if value_type == "boolean":
            raw = cell.getAttribute("booleanvalue")
            if raw is None:
                return None
            return str(raw).lower() == "true"
        if value_type == "float":
            raw = cell.getAttribute("value")
            if raw is None:
                return None
            try:
                if "." in raw or "e" in raw.lower():
                    return float(raw)
                return int(raw)
            except (TypeError, ValueError):
                return raw
        text_parts: list[str] = []
        for paragraph in cell.getElementsByType(text_ns.P):
            text_parts.append(str(paragraph))
        if not text_parts:
            return None
        return "".join(text_parts)

    @staticmethod
    def _load_odfpy_read() -> tuple[Any, Any, Any]:
        try:
            from odf import opendocument
            from odf import table as table_ns
            from odf import text as text_ns
        except ImportError as exc:
            raise ImportError(
                "OdsFormat requires odfpy. Install with `pip install pirn[ods]`."
            ) from exc
        return opendocument, table_ns, text_ns

    @staticmethod
    def _load_odfpy_write() -> tuple[Any, Any, Any]:
        try:
            from odf import table as table_ns
            from odf import text as text_ns
            from odf.opendocument import (
                OpenDocumentSpreadsheet,
            )
        except ImportError as exc:
            raise ImportError(
                "OdsFormat requires odfpy. Install with `pip install pirn[ods]`."
            ) from exc
        return OpenDocumentSpreadsheet, table_ns, text_ns
