"""``StringNormalizer`` — configurable string normalisation for text columns.

Each target column is transformed in the order below (each step is
individually optional):

1. Unicode normalise (NFC / NFD / NFKC / NFKD)
2. Lowercase
3. Strip leading / trailing whitespace
4. Remove punctuation (everything in :data:`string.punctuation`)
"""

from __future__ import annotations

import string
import unicodedata
from typing import Any, Literal, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class StringNormalizer(Knot):
    """Apply configurable normalisation steps to string columns."""

    def __init__(
        self,
        *,
        rows: Knot,
        columns: Sequence[str],
        lowercase: bool = True,
        strip: bool = True,
        remove_punctuation: bool = False,
        unicode_form: Literal["NFC", "NFD", "NFKC", "NFKD", "none"] = "NFC",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        col_tuple = tuple(columns)
        IdentifierValidator.validate_columns("columns", col_tuple)
        if unicode_form not in ("NFC", "NFD", "NFKC", "NFKD", "none"):
            raise ValueError(
                "StringNormalizer: unicode_form must be NFC/NFD/NFKC/NFKD/none"
            )
        self._columns = col_tuple
        self._lowercase = lowercase
        self._strip = strip
        self._remove_punctuation = remove_punctuation
        self._unicode_form = unicode_form
        self._punct_table = str.maketrans("", "", string.punctuation)
        super().__init__(rows=rows, _config=_config, **kwargs)

    def _normalise(self, value: str) -> str:
        if self._unicode_form != "none":
            value = unicodedata.normalize(self._unicode_form, value)
        if self._lowercase:
            value = value.lower()
        if self._strip:
            value = value.strip()
        if self._remove_punctuation:
            value = value.translate(self._punct_table)
        return value

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Apply normalisation to each target column in every row.

        Args:
            rows: Upstream rows as a list of dicts.

        Returns:
            Rows with target columns normalised in-place (values replaced).
        """
        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            for col in self._columns:
                if col in new_row and isinstance(new_row[col], str):
                    new_row[col] = self._normalise(new_row[col])
            result.append(new_row)
        return result
