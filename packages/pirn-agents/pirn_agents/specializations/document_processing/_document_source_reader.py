"""``_DocumentSourceReader`` — the single guarded reader for document sources.

Every document-processing loader reads its ``source`` through this collaborator so
the SSRF and path-traversal guards exist in exactly one place. Previously only
:class:`_DocumentLoader` carried them; ``_LoadAndChunk``, ``_QALoadAndChunk`` and
``_TranslationLoadAndChunk`` fetched arbitrary URLs and read arbitrary paths with
no guard at all (PIR-740).

Algorithm:
    1. Validate ``source`` is a non-empty string.
    2. Parse the scheme.
    3. For http(s): delegate host vetting to the shared ``SsrfGuard``, then stream
       the body with redirects disabled, capped at ``max_bytes``.
    4. For file:// or a bare path: resolve against ``allowed_root``, reject
       symlinks, enforce ``max_bytes``, then read as UTF-8.
    5. Return the decoded text.

References:
    - Python ipaddress module for SSRF IP classification.
    - httpx documentation for async HTTP client usage.
    - Python pathlib for safe path resolution.

Security:
    Fail-closed. Local reads require ``allowed_root``; reads resolving outside it
    (via ``..`` segments or symlinks) are rejected. ``max_bytes`` caps both a local
    file and a streamed URL response. URL host vetting is delegated to the shared
    :class:`~pirn_agents.tools.web._ssrf_guard.SsrfGuard` — the one implementation
    of that policy — and redirects are neither followed nor returned, so an
    allow-listed host cannot bounce the fetch to a private address.

    The optional ``web`` extra is resolved only *after* every check passes, so a
    hostile URL is rejected identically whether or not httpx is installed
    (PIR-739).

    Known limits, shared with every resolve-then-fetch guard in the codebase: the
    hostname is vetted by resolving it, then httpx re-resolves independently, so a
    short-TTL rebinding attacker can differ the two answers; ``socket.gethostbyname``
    checks only one A record; and IPv6 destinations fail closed as "unresolvable"
    rather than being classified.

Internal API.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents._require import _require
from pirn_agents.tools.web._ssrf_guard import SsrfGuard


@dataclass(frozen=True)
class _DocumentSourceReader(PirnOpaqueValue):
    """Read text from a local path or an HTTP(S) URL under a fixed security policy.

    Attributes
    ----------
    allowed_root:
        Directory that local reads must resolve within. ``None`` rejects local
        reads outright — the guard is fail-closed, never permissive by default.
    allowed_hosts:
        Optional hostname allow-list narrowing URL fetches beyond the IP checks.
    max_bytes:
        Maximum source size in bytes — caps a local file and a streamed URL body
        alike.
    request_timeout:
        HTTP request timeout in seconds.
    connect_timeout:
        HTTP connection timeout in seconds.
    resolver:
        Hostname->IP resolver handed to the ``SsrfGuard``; ``None`` uses real DNS.
        Excluded from equality so two readers with the same policy compare equal.
    """

    allowed_root: str | None = None
    allowed_hosts: tuple[str, ...] | None = None
    max_bytes: int = 100 * 1024 * 1024
    request_timeout: float = 10.0
    connect_timeout: float = 5.0
    resolver: Callable[[str], str] | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.max_bytes, int) or isinstance(self.max_bytes, bool):
            raise TypeError(
                f"_DocumentSourceReader: max_bytes must be an int, got {self.max_bytes!r}"
            )
        if self.max_bytes <= 0:
            raise ValueError(
                f"_DocumentSourceReader: max_bytes must be a positive int, got {self.max_bytes!r}"
            )

    async def read(self, source: str) -> str:
        """Read ``source`` and return its decoded text.

        Args:
            source: A local file path, a ``file://`` URI, or an ``http(s)://`` URL.

        Returns:
            The decoded UTF-8 text content of the source.

        Raises:
            TypeError: If source is not a non-empty string.
            ValueError: If the scheme is unsupported, the path resolves outside
                ``allowed_root``, the file exceeds ``max_bytes``, or the host is
                unresolvable, private/loopback/link-local, or not allow-listed.
        """
        if not isinstance(source, str) or not source:
            raise TypeError(
                f"_DocumentSourceReader: source must be a non-empty string, got {source!r}"
            )
        parsed = urlparse(source)
        scheme = parsed.scheme.lower()
        if scheme in ("http", "https"):
            return await self._fetch_url(source)
        if scheme in ("", "file"):
            return await self._read_file(parsed.path if scheme == "file" else source)
        raise ValueError(f"_DocumentSourceReader: unsupported source scheme: {parsed.scheme!r}")

    async def _read_file(self, path_str: str) -> str:
        if self.allowed_root is None:
            raise ValueError("_DocumentSourceReader: local file reads require allowed_root")
        root = Path(self.allowed_root).resolve(strict=True)
        candidate = Path(path_str)
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"_DocumentSourceReader: file does not exist: {path_str!r}") from exc
        if not resolved.is_relative_to(root):
            raise ValueError(
                f"_DocumentSourceReader: refusing to read outside allowed_root: {path_str!r}"
            )
        if candidate.is_symlink():
            raise ValueError(f"_DocumentSourceReader: refusing to read symlink: {path_str!r}")
        size = resolved.stat().st_size
        if size > self.max_bytes:
            raise ValueError(
                f"_DocumentSourceReader: file size {size} exceeds max_bytes {self.max_bytes}"
            )
        return await asyncio.to_thread(resolved.read_text, encoding="utf-8")

    async def _fetch_url(self, url: str) -> str:
        # Composes the shared SsrfGuard rather than re-deriving the IP predicate: it is
        # the one implementation of this policy, and its resolver is injectable so tests
        # need not monkeypatch socket.
        SsrfGuard(
            allowed_hosts=self.allowed_hosts,
            resolver=self.resolver,
        ).assert_public_host(url)
        # Resolved only after every check passes: the guard must reject a hostile URL
        # identically whether or not the optional ``web`` extra is installed (PIR-739).
        httpx = _require("web", "httpx")
        timeout = httpx.Timeout(self.request_timeout, connect=self.connect_timeout)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                if response.is_redirect:
                    raise ValueError(
                        f"_DocumentSourceReader: refusing to follow redirect from {url!r} "
                        f"to {response.headers.get('location')!r}"
                    )
                # Streamed and capped: an unbounded read would let a hostile or merely
                # oversized URL exhaust memory, and max_bytes must mean the same thing
                # for a URL as it does for a file.
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise ValueError(
                            f"_DocumentSourceReader: response body exceeds "
                            f"max_bytes {self.max_bytes}"
                        )
                    chunks.append(chunk)
                encoding = response.encoding or "utf-8"
                return b"".join(chunks).decode(encoding, errors="replace")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "allowed_root": self.allowed_root,
            # `is not None`, not truthiness: an empty tuple is a deny-all policy, and
            # collapsing it to None would audit it as "no allow-list" — the opposite.
            "allowed_hosts": (list(self.allowed_hosts) if self.allowed_hosts is not None else None),
            "max_bytes": self.max_bytes,
            "request_timeout": self.request_timeout,
            "connect_timeout": self.connect_timeout,
        }
