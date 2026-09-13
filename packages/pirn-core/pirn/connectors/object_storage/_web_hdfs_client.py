"""``_WebHDFSClient`` — thin synchronous WebHDFS adapter used by :class:`HDFSStore`."""

from __future__ import annotations

import asyncio
from typing import Any


class _WebHDFSClient:
    """Thin synchronous WebHDFS adapter (runs in asyncio.to_thread in prod)."""

    def __init__(self, *, base_url: str, user: str, session: Any) -> None:
        self._base_url = base_url
        self._user = user
        self._session = session

    async def get(self, path: str) -> bytes:
        return await asyncio.to_thread(self._sync_get, path)

    def _sync_get(self, path: str) -> bytes:
        url = f"{self._base_url}{path}?op=OPEN&user.name={self._user}"
        resp = self._session.get(url, allow_redirects=True)
        resp.raise_for_status()
        return resp.content

    async def put(self, path: str, data: bytes) -> None:
        await asyncio.to_thread(self._sync_put, path, data)

    def _sync_put(self, path: str, data: bytes) -> None:
        url = f"{self._base_url}{path}?op=CREATE&overwrite=true&user.name={self._user}"
        resp = self._session.put(url, data=data, allow_redirects=True)
        resp.raise_for_status()

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(self._sync_delete, path)

    def _sync_delete(self, path: str) -> None:
        url = f"{self._base_url}{path}?op=DELETE&user.name={self._user}"
        resp = self._session.delete(url)
        resp.raise_for_status()

    async def list(self, path: str) -> list[str]:
        return await asyncio.to_thread(self._sync_list, path)

    def _sync_list(self, path: str) -> list[str]:
        url = f"{self._base_url}{path}?op=LISTSTATUS&user.name={self._user}"
        resp = self._session.get(url)
        resp.raise_for_status()
        statuses = resp.json().get("FileStatuses", {}).get("FileStatus", [])
        return [f"{path.rstrip('/')}/{s['pathSuffix']}" for s in statuses if s.get("pathSuffix")]

    def close(self) -> None:
        self._session.close()
