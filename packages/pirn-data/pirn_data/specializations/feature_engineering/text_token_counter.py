"""``TextTokenCounter`` — count tokens in a text column.

Uses tiktoken if available, falls back to whitespace splitting otherwise.
No hard import of tiktoken — the import is attempted at process time.

Algorithm:
    1. Receive resolved ``rows``, ``text_column``, ``output_column``, and
       ``tiktoken_encoding`` in ``process()``.
    2. Validate ``text_column`` and ``output_column`` identifiers; validate
       that ``rows`` is a list or tuple.
    3. Attempt to import tiktoken and build an encoding-based counter; fall
       back to whitespace-split counting if the import fails.
    4. For each row extract the text value (coerce non-strings; treat
       ``None`` as empty), count tokens, and append ``output_column``.
    5. Return a dict with ``succeeded``, enriched ``rows``, and
       ``tokenizer`` indicating which counter was used.

References:
    [1] tiktoken — OpenAI tokenizer library (optional dependency):
        https://github.com/openai/tiktoken
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.data_optional_dependency import DataOptionalDependency
from pirn_data.identifier_validator import IdentifierValidator
from pirn_data.value_shape import ValueShape


class TextTokenCounter(Knot):
    """Count tokens in a text column using tiktoken or whitespace split."""

    def __init__(
        self,
        *,
        rows: Knot | list[dict[str, Any]],
        text_column: Knot | str,
        output_column: Knot | str,
        tiktoken_encoding: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            text_column=text_column,
            output_column=output_column,
            tiktoken_encoding=tiktoken_encoding,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _make_counter(tiktoken_encoding: str) -> tuple[Callable[[str], int], str]:
        """Return the token counter and the label of the tokenizer behind it.

        tiktoken is optional and imported lazily, so the knot works — with
        whitespace splitting — when it is absent.
        """
        try:
            tiktoken = DataOptionalDependency.require("tiktoken", extra="tiktoken")
        except ImportError:
            return (lambda text: len(text.split())), "whitespace"
        enc = tiktoken.get_encoding(tiktoken_encoding)
        return (lambda text: len(enc.encode(text))), f"tiktoken:{tiktoken_encoding}"

    async def process(
        self,
        *,
        rows: Any,
        text_column: Any,
        output_column: Any,
        tiktoken_encoding: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not ValueShape.is_list_or_tuple(rows):
            raise TypeError("TextTokenCounter: rows must be a list or tuple of dicts")
        if not isinstance(text_column, str) or not text_column:
            raise ValueError("TextTokenCounter: text_column must be a non-empty string")
        IdentifierValidator.validate_column("text_column", text_column)
        IdentifierValidator.validate_column("output_column", output_column)
        counter, tokenizer = self._make_counter(tiktoken_encoding)
        enriched: list[dict[str, Any]] = []
        for row in rows:
            text = row.get(text_column, "")
            if not isinstance(text, str):
                text = str(text) if text is not None else ""
            enriched.append({**row, output_column: counter(text)})
        return {
            "succeeded": True,
            "rows": enriched,
            "tokenizer": tokenizer,
        }
