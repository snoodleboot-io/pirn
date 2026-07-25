"""``_LoadAndChunk`` — internal helper Knot for :class:`DocumentSummarizerPipeline`.

Algorithm:
    1. Receive resolved ``source`` and ``chunk_size``.
    2. Validate source is a non-empty string and chunk_size is positive.
    3. Load text from a local file path or http(s):// URL.
    4. Slide a non-overlapping window of ``chunk_size`` over the text.
    5. Return the resulting list of chunk strings.

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


class _LoadAndChunk(Knot):
    """Read the source text and split it into fixed-size chunks."""

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
        """Load text from source and split it into fixed-size chunks.

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
            ValueError: If chunk_size is not a positive integer, or the source is
                rejected by the SSRF / path-traversal guard.
        """
        if not isinstance(source, str) or not source:
            raise TypeError(
                f"DocumentSummarizerPipeline: source must be a non-empty string, got {source!r}"
            )
        if chunk_size <= 0:
            raise ValueError(
                f"DocumentSummarizerPipeline: chunk_size must be positive, got {chunk_size!r}"
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
