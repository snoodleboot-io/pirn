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
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class TextTokenCounter(Knot):
    """Count tokens in a text column using tiktoken or whitespace split."""

    def __init__(
        self,
        *,
        rows: Knot | list,
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
    def _make_counter(tiktoken_encoding: str) -> Any:
        try:
            import tiktoken

            enc = tiktoken.get_encoding(tiktoken_encoding)

            def _count(text: str) -> int:
                return len(enc.encode(text))

            return _count
        except ImportError:

            def _count(text: str) -> int:  # type: ignore[misc]
                return len(text.split())

            return _count

    async def process(
        self,
        *,
        rows: Any,
        text_column: Any,
        output_column: Any,
        tiktoken_encoding: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(rows, (list, tuple)):
            raise TypeError("TextTokenCounter: rows must be a list or tuple of dicts")
        if not isinstance(text_column, str) or not text_column:
            raise ValueError("TextTokenCounter: text_column must be a non-empty string")
        IdentifierValidator.validate_column("text_column", text_column)
        IdentifierValidator.validate_column("output_column", output_column)
        try:
            import tiktoken as _tiktoken

            _ = _tiktoken
            tokenizer = f"tiktoken:{tiktoken_encoding}"
        except ImportError:
            tokenizer = "whitespace"
        counter = self._make_counter(tiktoken_encoding)
        enriched = []
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
