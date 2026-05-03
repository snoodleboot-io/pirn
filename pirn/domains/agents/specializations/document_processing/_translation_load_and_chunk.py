"""``_TranslationLoadAndChunk`` — internal helper Knot for :class:`DocumentTranslationPipeline`.

Reads source text and splits it into fixed-size chunks. Internal API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class _TranslationLoadAndChunk(Knot):
    """Read the source text and split into fixed-size chunks."""

    def __init__(
        self,
        *,
        source: Knot | str,
        chunk_size: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source=source,
            chunk_size=chunk_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source: str,
        chunk_size: int,
        **_: Any,
    ) -> list[str]:
        """Load text from source and split it into fixed-size chunks for translation.

        Args:
            source: A local file path or http(s):// URL to read text from.
            chunk_size: The maximum character length of each chunk.

        Returns:
            A list of fixed-size text chunk strings; empty if the source yields no text.

        Raises:
            TypeError: If source is not a non-empty string.
        """
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentTranslationPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        text = await _TranslationLoadAndChunk._load_text(source)
        if not text:
            return []
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    @staticmethod
    async def _load_text(source: str) -> str:
        parsed = urlparse(source)
        if parsed.scheme in ("http", "https"):
            try:
                import httpx
            except ImportError as exc:
                raise ImportError(
                    "DocumentTranslationPipeline: http(s) sources require httpx; "
                    "install via `pip install pirn[http]`"
                ) from exc
            async with httpx.AsyncClient() as client:
                response = await client.get(source)
                response.raise_for_status()
                return response.text
        return Path(source).read_text(encoding="utf-8")
