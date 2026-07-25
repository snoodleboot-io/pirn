"""``_DocumentLoader`` — internal helper Knot for :class:`DocumentIngestionPipeline`.

Algorithm:
    1. Receive resolved ``source`` and optional security parameters.
    2. Validate ``max_bytes`` is positive and ``source`` is a non-empty string.
    3. Parse the URL scheme of ``source``.
    4. For http(s) schemes: resolve hostname, reject private/loopback/reserved IPs
       (SSRF guard), optionally check against ``allowed_hosts``, then fetch via httpx.
    5. For file/local paths: resolve against ``allowed_root`` (path-traversal guard),
       reject symlinks, check file size against ``max_bytes``, then read as UTF-8.
    6. Return the decoded text content.


References:
    - Python ipaddress module for SSRF IP classification.
    - httpx documentation for async HTTP client usage.
    - Python pathlib for safe path resolution.

Security:
    Local file reads require ``allowed_root``; reads outside that root
    (including via ``..`` segments or symlinks) are rejected. File size
    is capped by ``max_bytes``. URL fetches reject hostnames resolving to
    private, loopback, link-local, reserved, or multicast IPs. An optional
    ``allowed_hosts`` allow-list narrows further.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.document_processing._document_source_reader import (
    _DocumentSourceReader,
)


class _DocumentLoader(Knot):
    """Read text from a local file path or fetch it over HTTP(S)."""

    def __init__(
        self,
        *,
        source: Knot | str,
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
        allowed_root: str | None = None,
        allowed_hosts: tuple[str, ...] | None = None,
        max_bytes: int = _DocumentSourceReader.max_bytes,
        request_timeout: float = _DocumentSourceReader.request_timeout,
        connect_timeout: float = _DocumentSourceReader.connect_timeout,
        **_: Any,
    ) -> str:
        """Read text from a local file path or fetch it over HTTP(S) and return the content.

        Args:
            source: A local file path, a file:// URI, or an http(s):// URL to read from.
            allowed_root: Directory root that local file reads must stay within.
            allowed_hosts: Optional allow-list of hostnames for URL fetches.
            max_bytes: Maximum file size in bytes (default 100 MiB).
            request_timeout: HTTP request timeout in seconds.
            connect_timeout: HTTP connection timeout in seconds.

        Returns:
            The decoded text content of the source.

        Raises:
            TypeError: If source is not a non-empty string.
            ValueError: If max_bytes <= 0, source scheme is unsupported, the file is
                outside allowed_root, or the resolved host is private or loopback.
        """
        if not isinstance(source, str) or not source:
            raise TypeError(
                f"DocumentIngestionPipeline: source must be a non-empty string, got {source!r}"
            )
        reader = _DocumentSourceReader(
            allowed_root=allowed_root,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            request_timeout=request_timeout,
            connect_timeout=connect_timeout,
        )
        return await reader.read(source)
