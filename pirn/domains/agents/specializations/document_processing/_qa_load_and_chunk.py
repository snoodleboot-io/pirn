"""``_QALoadAndChunk`` — internal helper Knot for :class:`DocumentQAPipeline`.

Algorithm:
    1. Receive resolved ``source`` and ``chunk_size``.
    2. Load text from a local file path or http(s):// URL.
    3. Slide a non-overlapping window of ``chunk_size`` over the text.
    4. Return the resulting list of chunk strings for downstream QA retrieval.

    ``chunks[i] = text[i*chunk_size : (i+1)*chunk_size]``.

References:
    - Python pathlib documentation for file reading.
    - httpx documentation for async HTTP requests.

Internal API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class _QALoadAndChunk(Knot):
    """Read the source text and return fixed-size chunks (default ~1000 chars)."""

    def __init__(
        self,
        *,
        source: Knot | str,
        chunk_size: Knot | int,
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
        """Load text from source and return fixed-size chunks for downstream QA retrieval.

        Args:
            source: A local file path or http(s):// URL to read text from.
            chunk_size: The maximum character length of each chunk.

        Returns:
            A list of fixed-size text chunk strings; empty if the source yields no text.
        """
        text = await _QALoadAndChunk._load_text(source)
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
                    "DocumentQAPipeline: http(s) sources require httpx; "
                    "install via `pip install pirn[http]`"
                ) from exc
            async with httpx.AsyncClient() as client:
                response = await client.get(source)
                response.raise_for_status()
                return response.text
        return Path(source).read_text(encoding="utf-8")
