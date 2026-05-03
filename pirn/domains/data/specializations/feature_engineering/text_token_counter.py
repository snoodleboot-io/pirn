"""``TextTokenCounter`` — counts tokens in a text column.

Uses tiktoken if available, falls back to whitespace splitting otherwise.
No hard import of tiktoken — the import is attempted at process time.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class TextTokenCounter(SubTapestry):
    """Count tokens in a text column using tiktoken or whitespace split."""

    def __init__(
        self,
        *,
        rows: Sequence[dict[str, Any]],
        text_column: str,
        output_column: str = "token_count",
        tiktoken_encoding: str = "cl100k_base",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(rows, (list, tuple)):
            raise TypeError(
                "TextTokenCounter: rows must be a list or tuple of dicts"
            )
        if not isinstance(text_column, str) or not text_column:
            raise ValueError(
                "TextTokenCounter: text_column must be a non-empty string"
            )
        IdentifierValidator.validate_column("text_column", text_column)
        IdentifierValidator.validate_column("output_column", output_column)
        self._rows = list(rows)
        self._text_column = text_column
        self._output_column = output_column
        self._tiktoken_encoding = tiktoken_encoding
        super().__init__(_config=_config, **kwargs)

    def _make_counter(self) -> Any:
        try:
            import tiktoken  # noqa: PLC0415

            enc = tiktoken.get_encoding(self._tiktoken_encoding)

            def _count(text: str) -> int:
                return len(enc.encode(text))

            return _count
        except ImportError:
            def _count(text: str) -> int:  # type: ignore[misc]
                return len(text.split())

            return _count

    async def process(self, **_: Any) -> dict[str, Any]:
        """Count tokens in the text column for each row, returning enriched records.

        Returns:
            A dict with keys ``succeeded``, ``rows`` (list of input dicts
            with the token count added), and ``tokenizer`` indicating which
            tokenizer was used.
        """
        try:
            import tiktoken as _tiktoken  # noqa: PLC0415

            _ = _tiktoken
            tokenizer = f"tiktoken:{self._tiktoken_encoding}"
        except ImportError:
            tokenizer = "whitespace"
        counter = self._make_counter()
        enriched = []
        for row in self._rows:
            text = row.get(self._text_column, "")
            if not isinstance(text, str):
                text = str(text) if text is not None else ""
            enriched.append({**row, self._output_column: counter(text)})
        return {
            "succeeded": True,
            "rows": enriched,
            "tokenizer": tokenizer,
        }
