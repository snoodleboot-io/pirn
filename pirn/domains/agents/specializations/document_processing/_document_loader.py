"""``_DocumentLoader`` — internal helper Knot for :class:`DocumentIngestionPipeline`.

Reads text from a local file path or fetches it over HTTP(S). Internal API.

Security
--------
Local file reads require the caller to pass an ``allowed_root`` directory
at construction time; reads outside that root (including those reached via
``..`` segments or symlinks) are rejected. File size is capped by
``max_bytes``. URL fetches reject any hostname that resolves to a private,
loopback, link-local, reserved, or multicast IP, defending against SSRF
into the loopback interface or the cloud-metadata service. An optional
``allowed_hosts`` allow-list narrows further.
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


class _DocumentLoader(Knot):
    """Read text from a local file path or fetch it over HTTP(S)."""

    def __init__(
        self,
        *,
        source: Knot | str,
        _config: KnotConfig,
        allowed_root: str | None = None,
        allowed_hosts: tuple[str, ...] | None = None,
        max_bytes: int = 100 * 1024 * 1024,
        request_timeout: float = 10.0,
        connect_timeout: float = 5.0,
        **kwargs: Any,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError(
                "_DocumentLoader: max_bytes must be a positive int, "
                f"got {max_bytes!r}"
            )
        self._allowed_root = allowed_root
        self._allowed_hosts = allowed_hosts
        self._max_bytes = max_bytes
        self._request_timeout = request_timeout
        self._connect_timeout = connect_timeout
        super().__init__(source=source, _config=_config, **kwargs)

    async def process(self, source: str, **_: Any) -> str:
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentIngestionPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        parsed = urlparse(source)
        scheme = parsed.scheme.lower()
        if scheme in ("http", "https"):
            return await self._fetch_url(source)
        if scheme == "" or scheme == "file":
            local_path = parsed.path if scheme == "file" else source
            return await self._read_file(local_path)
        raise ValueError(
            f"_DocumentLoader: unsupported source scheme: {parsed.scheme!r}"
        )

    async def _read_file(self, path_str: str) -> str:
        if self._allowed_root is None:
            raise ValueError(
                "_DocumentLoader: local file reads require allowed_root "
                "constructor argument"
            )
        root = Path(self._allowed_root).resolve(strict=True)
        candidate = Path(path_str)
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(
                f"_DocumentLoader: file does not exist: {path_str!r}"
            ) from exc
        if not resolved.is_relative_to(root):
            raise ValueError(
                f"_DocumentLoader: refusing to read outside allowed_root: "
                f"{path_str!r}"
            )
        if candidate.is_symlink():
            raise ValueError(
                f"_DocumentLoader: refusing to read symlink: {path_str!r}"
            )
        size = resolved.stat().st_size
        if size > self._max_bytes:
            raise ValueError(
                f"_DocumentLoader: file size {size} exceeds max_bytes "
                f"{self._max_bytes}"
            )
        return await asyncio.to_thread(resolved.read_text, encoding="utf-8")

    async def _fetch_url(self, url: str) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "DocumentIngestionPipeline: http(s) sources require httpx; "
                "install via `pip install pirn[http]`"
            ) from exc
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError(
                f"_DocumentLoader: URL has no hostname: {url!r}"
            )
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        except (socket.gaierror, ValueError) as exc:
            raise ValueError(
                f"_DocumentLoader: refusing to fetch unresolvable host: "
                f"{hostname!r}"
            ) from exc
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError(
                f"_DocumentLoader: refusing to fetch "
                f"private/loopback/link-local: {hostname!r} -> {ip}"
            )
        if (
            self._allowed_hosts is not None
            and hostname not in self._allowed_hosts
        ):
            raise ValueError(
                f"_DocumentLoader: host {hostname!r} not in allowed_hosts"
            )
        timeout = httpx.Timeout(self._request_timeout, connect=self._connect_timeout)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
