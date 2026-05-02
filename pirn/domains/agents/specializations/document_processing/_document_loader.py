"""``_DocumentLoader`` — internal helper Knot for :class:`DocumentIngestionPipeline`.

Reads text from a local file path or fetches it over HTTP(S). Internal API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class _DocumentLoader(Knot):
    """Read text from a local file path or fetch it over HTTP(S)."""

    def __init__(
        self,
        *,
        source: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(source=source, _config=_config, **kwargs)

    async def process(self, source: str, **_: Any) -> str:
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentIngestionPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        parsed = urlparse(source)
        if parsed.scheme in ("http", "https"):
            return await self._fetch_url(source)
        return self._read_file(source)

    @staticmethod
    def _read_file(path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    @staticmethod
    async def _fetch_url(url: str) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "DocumentIngestionPipeline: http(s) sources require httpx; "
                "install via `pip install pirn[http]`"
            ) from exc
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
