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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.document_processing._document_source_reader import (
    _DocumentSourceReader,
)


class _QALoadAndChunk(Knot):
    """Read the source text and return fixed-size chunks (default ~1000 chars)."""

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
        """Load text from source and return fixed-size chunks for downstream QA retrieval.

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
