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

import asyncio
import ipaddress
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents._require import _require


class _DocumentLoader(Knot):
    """Read text from a local file path or fetch it over HTTP(S)."""

    def __init__(
        self,
        *,
        source: Knot | str,
        _config: KnotConfig,
        allowed_root: Knot | str | None = None,
        allowed_hosts: Knot | tuple[str, ...] | None = None,
        max_bytes: Knot | int = 100 * 1024 * 1024,
        request_timeout: Knot | float = 10.0,
        connect_timeout: Knot | float = 5.0,
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
        max_bytes: int = 100 * 1024 * 1024,
        request_timeout: float = 10.0,
        connect_timeout: float = 5.0,
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
        if max_bytes <= 0:
            raise ValueError(
                f"_DocumentLoader: max_bytes must be a positive int, got {max_bytes!r}"
            )
        if not isinstance(source, str) or not source:
            raise TypeError(
                f"DocumentIngestionPipeline: source must be a non-empty string, got {source!r}"
            )
        parsed = urlparse(source)
        scheme = parsed.scheme.lower()
        if scheme in ("http", "https"):
            return await self._fetch_url(source, allowed_hosts, request_timeout, connect_timeout)
        if scheme == "" or scheme == "file":
            local_path = parsed.path if scheme == "file" else source
            return await self._read_file(local_path, allowed_root, max_bytes)
        raise ValueError(f"_DocumentLoader: unsupported source scheme: {parsed.scheme!r}")

    async def _read_file(self, path_str: str, allowed_root: str | None, max_bytes: int) -> str:
        if allowed_root is None:
            raise ValueError(
                "_DocumentLoader: local file reads require allowed_root constructor argument"
            )
        root = Path(allowed_root).resolve(strict=True)
        candidate = Path(path_str)
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"_DocumentLoader: file does not exist: {path_str!r}") from exc
        if not resolved.is_relative_to(root):
            raise ValueError(
                f"_DocumentLoader: refusing to read outside allowed_root: {path_str!r}"
            )
        if candidate.is_symlink():
            raise ValueError(f"_DocumentLoader: refusing to read symlink: {path_str!r}")
        size = resolved.stat().st_size
        if size > max_bytes:
            raise ValueError(f"_DocumentLoader: file size {size} exceeds max_bytes {max_bytes}")
        return await asyncio.to_thread(resolved.read_text, encoding="utf-8")

    async def _fetch_url(
        self,
        url: str,
        allowed_hosts: tuple[str, ...] | None,
        request_timeout: float,
        connect_timeout: float,
    ) -> str:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"_DocumentLoader: URL has no hostname: {url!r}")
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        except (socket.gaierror, ValueError) as exc:
            raise ValueError(
                f"_DocumentLoader: refusing to fetch unresolvable host: {hostname!r}"
            ) from exc
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(
                f"_DocumentLoader: refusing to fetch "
                f"private/loopback/link-local: {hostname!r} -> {ip}"
            )
        if allowed_hosts is not None and hostname not in allowed_hosts:
            raise ValueError(f"_DocumentLoader: host {hostname!r} not in allowed_hosts")
        # Resolved only after the SSRF and allow-list checks pass: the guard must reject a
        # hostile URL identically whether or not the optional ``web`` extra is installed.
        httpx = _require("web", "httpx")
        timeout = httpx.Timeout(request_timeout, connect=connect_timeout)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
