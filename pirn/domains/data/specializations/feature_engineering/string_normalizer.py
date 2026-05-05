"""``StringNormalizer`` — configurable string normalisation for text columns.

Each target column is transformed in the order below (each step is
individually optional):

1. Unicode normalise (NFC / NFD / NFKC / NFKD)
2. Lowercase
3. Strip leading / trailing whitespace
4. Remove punctuation (everything in :data:`string.punctuation`)

Algorithm:
    1. Receive resolved ``rows``, ``columns``, ``lowercase``, ``strip``,
       ``remove_punctuation``, and ``unicode_form`` in ``process()``.
    2. Validate column identifiers and ``unicode_form`` membership.
    3. For each row apply the normalisation pipeline to each target column
       (only if the value is a string; non-string values are left intact).
    4. Return the normalised row list.

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

import string
import unicodedata
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)
_VALID_UNICODE_FORMS = frozenset(("NFC", "NFD", "NFKC", "NFKD", "none"))


class StringNormalizer(Knot):
    """Apply configurable normalisation steps to string columns."""

    def __init__(
        self,
        *,
        rows: Knot | list,
        columns: Knot | tuple[str, ...],
        lowercase: Knot | bool,
        strip: Knot | bool,
        remove_punctuation: Knot | bool,
        unicode_form: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            columns=columns,
            lowercase=lowercase,
            strip=strip,
            remove_punctuation=remove_punctuation,
            unicode_form=unicode_form,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _normalise(
        value: str,
        unicode_form: str,
        lowercase: bool,
        strip: bool,
        remove_punctuation: bool,
    ) -> str:
        if unicode_form != "none":
            value = unicodedata.normalize(unicode_form, value)
        if lowercase:
            value = value.lower()
        if strip:
            value = value.strip()
        if remove_punctuation:
            value = value.translate(_PUNCT_TABLE)
        return value

    async def process(
        self,
        *,
        rows: Any,
        columns: Any,
        lowercase: Any,
        strip: Any,
        remove_punctuation: Any,
        unicode_form: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        col_tuple = tuple(columns)
        IdentifierValidator.validate_columns("columns", col_tuple)
        if unicode_form not in _VALID_UNICODE_FORMS:
            raise ValueError("StringNormalizer: unicode_form must be NFC/NFD/NFKC/NFKD/none")
        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            for col in col_tuple:
                if col in new_row and isinstance(new_row[col], str):
                    new_row[col] = self._normalise(
                        new_row[col], unicode_form, lowercase, strip, remove_punctuation
                    )
            result.append(new_row)
        return result
