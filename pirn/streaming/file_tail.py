"""File tailer — yield each new line appended to a file."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from pirn.streaming.base import StreamingSource


class FileTailSource(StreamingSource):
    """Tails a file like ``tail -f``; yields each new line.

    Useful for log-processing pipelines.  The source seeks to the end
    of the file at start (so existing content isn't replayed); set
    ``from_start=True`` to consume the whole file before tailing.

    The poll interval defaults to 0.1s.  For high-throughput files
    consider a notification-based source (inotify on Linux) — that's
    a future extension.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        parameter_name: str,
        from_start: bool = False,
        poll_seconds: float = 0.1,
        encoding: str = "utf-8",
        name: str = "FileTailSource",
    ) -> None:
        self._path = Path(path)
        self._parameter_name = parameter_name
        self._from_start = from_start
        self._poll = poll_seconds
        self._encoding = encoding
        self._name = name
        self._closed = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def parameter_name(self) -> str:
        return self._parameter_name

    async def stream(self) -> AsyncIterator[str]:
        # Open the file; seek to end unless explicitly requested.
        # Reads happen via asyncio.to_thread to avoid blocking the loop.
        f = await asyncio.to_thread(self._path.open, "r", encoding=self._encoding)
        try:
            if not self._from_start:
                await asyncio.to_thread(f.seek, 0, 2)  # seek to end
            buffer = ""
            while not self._closed:
                chunk = await asyncio.to_thread(f.readline)
                if chunk:
                    if chunk.endswith("\n"):
                        line = (buffer + chunk).rstrip("\n")
                        buffer = ""
                        yield line
                    else:
                        # Partial line; accumulate until newline.
                        buffer += chunk
                else:
                    # No new data; sleep and try again.
                    await asyncio.sleep(self._poll)
        finally:
            await asyncio.to_thread(f.close)

    async def close(self) -> None:
        self._closed = True
