"""``AdvisoryFileLock`` — the "is this run still alive?" probe, fail-safe by design.

:class:`~pirn.core.transport.filesystem_transport.FilesystemTransport` marks a
live run by holding an exclusive advisory lock on a file inside its run
directory, and its sweeper deletes a run directory only when that lock is *not*
held. That makes :meth:`AdvisoryFileLock.is_held` a deletion gate, so the
interesting case is not "held" or "free" but **"cannot tell"**.

Every unknown answers "held". A false "held" leaks a directory until the next
sweep after the real holder exits; a false "free" hands ``shutil.rmtree`` a
directory a running process is still writing into (PIR-873). The two mistakes are
not comparable, so the ambiguous cases — no advisory-lock primitive on this
interpreter, a lock file that cannot be opened, an ``OSError`` from the lock call
itself — all resolve to "held".

The primitive is ``fcntl.flock`` on POSIX and ``msvcrt.locking`` on Windows. Both
are stdlib and platform-exclusive, so each is imported inside the method that
uses it rather than at module scope.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import IO

_log = logging.getLogger(__name__)


class AdvisoryFileLock:
    """Take, release, and probe an exclusive advisory lock on a file."""

    #: Bytes locked on Windows. ``msvcrt.locking`` needs a non-zero length and
    #: locks a byte range rather than the whole file; one byte at offset 0 is
    #: enough for a mutual-exclusion marker on a zero-length lock file.
    _windows_lock_bytes = 1

    def acquire(self, path: Path) -> IO[str] | None:
        """Create *path* and hold an exclusive lock on it.

        Args:
            path: The lock file. Its parent directory must exist.

        Returns:
            The open handle whose lifetime holds the lock — keep it and pass it
            to :meth:`release` — or ``None`` when the lock could not be taken
            (another process holds it, the file could not be opened, or this
            interpreter has no advisory-lock primitive).
        """
        if not self.platform_supported():
            _log.warning(
                "AdvisoryFileLock: no advisory-lock primitive on this interpreter "
                "(neither fcntl nor msvcrt); %s is a marker only, and abandoned-run "
                "sweeping will leave directories alone rather than risk deleting a live one",
                path,
            )
            return None
        try:
            handle = path.open("w")
        except OSError as exc:
            _log.warning("AdvisoryFileLock: could not open lock file %s: %s", path, exc)
            return None
        try:
            if self._try_lock(handle):
                return handle
        except OSError as exc:
            _log.warning("AdvisoryFileLock: could not lock %s: %s", path, exc)
        handle.close()
        return None

    def release(self, handle: IO[str]) -> None:
        """Unlock and close a handle from :meth:`acquire`; safe to call twice."""
        if handle.closed:
            return
        try:
            self._unlock(handle)
        except OSError as exc:
            _log.warning("AdvisoryFileLock: could not unlock %s: %s", handle.name, exc)
        try:
            handle.close()
        except OSError as exc:
            _log.warning("AdvisoryFileLock: could not close %s: %s", handle.name, exc)

    def is_held(self, path: Path) -> bool:
        """Whether some process holds the lock on *path* — ``True`` when unknown.

        The caller is a sweeper deciding whether to delete the directory *path*
        lives in, so every answer this method is not sure of is ``True``. See the
        module docstring for why the two mistakes are not symmetric.

        Args:
            path: The lock file.

        Returns:
            ``False`` only when the lock file exists and this process
            successfully took and released the lock — proof that nobody else
            holds it. ``False`` also for a lock file that does not exist, since
            there is then nothing to hold.
        """
        if not path.exists():
            return False
        if not self.platform_supported():
            return True
        try:
            with path.open("r+") as handle:
                if not self._try_lock(handle):
                    return True
                self._unlock(handle)
                return False
        except OSError as exc:
            _log.warning(
                "AdvisoryFileLock: could not probe lock %s (%s); assuming it is held, "
                "because reporting it free would invite deleting a live run directory",
                path,
                exc,
            )
            return True

    @staticmethod
    def platform_supported() -> bool:
        """Whether this interpreter offers an advisory-lock primitive at all.

        Asked with :func:`importlib.util.find_spec` rather than a ``try: import``
        so the answer needs no imported-and-unused name.
        """
        return any(importlib.util.find_spec(name) is not None for name in ("fcntl", "msvcrt"))

    @classmethod
    def _try_lock(cls, handle: IO[str]) -> bool:
        """Take an exclusive non-blocking lock; ``False`` when another holder has it.

        Raises:
            OSError: If the lock call fails for a reason other than contention
                (a filesystem with no lock support, for instance). The callers
                turn that into "assume held".
        """
        try:
            import fcntl
        except ImportError:
            pass
        else:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            return True
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, cls._windows_lock_bytes)
        except OSError:
            # Windows reports contention as a plain OSError, indistinguishable
            # from a hard failure, so contention is the reading that keeps the
            # sweeper conservative.
            return False
        return True

    @classmethod
    def _unlock(cls, handle: IO[str]) -> None:
        """Release a lock taken by :meth:`_try_lock`."""
        try:
            import fcntl
        except ImportError:
            pass
        else:
            fcntl.flock(handle, fcntl.LOCK_UN)
            return
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, cls._windows_lock_bytes)
