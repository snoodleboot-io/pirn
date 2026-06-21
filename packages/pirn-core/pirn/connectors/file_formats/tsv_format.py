"""``TsvFormat`` — tab-separated values, a thin :class:`CsvFormat` subclass.

Identical mechanics to :class:`CsvFormat`; the default field delimiter
is the tab character. Stdlib ``csv`` module — no optional dependency.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.connectors.file_formats.csv_format import CsvFormat


class TsvFormat(CsvFormat):
    """Tab-separated values backed by stdlib ``csv``.

    Args:
        delimiter: Single-character field delimiter. Defaults to ``"\\t"``.
        quotechar: Single-character quote delimiter. Defaults to ``'"'``.
        has_header: When ``True``, the first row holds column names.
        column_names: Required when ``has_header=False``.
        encoding: Text encoding. Defaults to ``"utf-8"``.
    """

    def __init__(
        self,
        delimiter: str = "\t",
        quotechar: str = '"',
        has_header: bool = True,
        column_names: Sequence[str] | None = None,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__(
            delimiter=delimiter,
            quotechar=quotechar,
            has_header=has_header,
            column_names=column_names,
            encoding=encoding,
        )

    @property
    def name(self) -> str:
        return "tsv"
