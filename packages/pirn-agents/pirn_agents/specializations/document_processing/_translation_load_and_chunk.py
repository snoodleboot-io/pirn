"""``_TranslationLoadAndChunk`` — internal helper Knot for :class:`DocumentTranslationPipeline`.

Reads source text and splits it into fixed-size chunks. Internal API.

Algorithm:
    1. Resolve the source: if a URL (``http``/``https``), fetch via HTTP; otherwise read
       from the local filesystem path.
    2. Partition the raw text into non-overlapping windows of exactly ``chunk_size``
       characters, collecting any remainder as the final (shorter) chunk.

Math:
    No numeric computation — chunk boundaries are fixed-size character offsets:
    ``chunk_i = text[i * chunk_size : (i + 1) * chunk_size]``.

References:
    - No external references — chunking strategy is a fixed-size partition with no
      overlap, in contrast to the sliding-window approach used in QA/ingestion pipelines.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.document_processing._document_source_reader import (
    _DocumentSourceReader,
)


class _TranslationLoadAndChunk(Knot):
    """Read the source text and split into fixed-size chunks."""

    def __init__(
        self,
        *,
        source: Knot | str,
        chunk_size: Knot | int,
        _config: KnotConfig,
        allowed_root: Knot | str | None = None,
        allowed_hosts: Knot | tuple[str, ...] | None = None,
        max_bytes: Knot | int = _DocumentSourceReader.max_bytes,
        request_timeout: Knot | float = _DocumentSourceReader.request_timeout,
        connect_timeout: Knot | float = _DocumentSourceReader.connect_timeout,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source=source,
            chunk_size=chunk_size,
            allowed_root=allowed_root,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            request_timeout=request_timeout,
            connect_timeout=connect_timeout,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source: str,
        chunk_size: int,
        allowed_root: str | None = None,
        allowed_hosts: tuple[str, ...] | None = None,
        max_bytes: int = _DocumentSourceReader.max_bytes,
        request_timeout: float = _DocumentSourceReader.request_timeout,
        connect_timeout: float = _DocumentSourceReader.connect_timeout,
        **_: Any,
    ) -> list[str]:
        """Load text from source and split it into fixed-size chunks for translation.

        Args:
            source: A local file path or http(s):// URL to read text from.
            chunk_size: The maximum character length of each chunk.
            allowed_root: Directory root that local file reads must stay within.
            allowed_hosts: Optional allow-list of hostnames for URL fetches.
            max_bytes: Maximum file size in bytes (default 100 MiB).
            request_timeout: HTTP request timeout in seconds.
            connect_timeout: HTTP connection timeout in seconds.

        Returns:
            A list of fixed-size text chunk strings; empty if the source yields no text.

        Raises:
            TypeError: If source is not a non-empty string.
            ValueError: If the source is rejected by the SSRF / path-traversal guard.
        """
        if not isinstance(source, str) or not source:
            raise TypeError(
                f"DocumentTranslationPipeline: source must be a non-empty string, got {source!r}"
            )
        reader = _DocumentSourceReader(
            allowed_root=allowed_root,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            request_timeout=request_timeout,
            connect_timeout=connect_timeout,
        )
        text = await reader.read(source)
        if not text:
            return []
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
