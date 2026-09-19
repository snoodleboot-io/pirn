"""``AdvisoryFileLock`` answers "held" whenever it cannot prove otherwise (PIR-873).

``FilesystemTransport.sweep_abandoned`` calls ``_is_lock_held`` and then
``shutil.rmtree``, so this is a deletion gate. It used to return ``False`` — safe
to delete — whenever ``import fcntl`` failed (every Windows run) or opening the
lock file raised ``OSError``, which sweeps the run directory of a process still
writing into it. Each test below pins one of those unknowns to "held".
"""

from __future__ import annotations

import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path

from pirn.core.transport.advisory_file_lock import AdvisoryFileLock


def _hold_lock(path_text: str, ready_name: str, hold_seconds: float) -> None:
    """Hold the lock in a separate process, then release it.

    A separate *process*, not a thread: ``fcntl.flock`` is per open-file-
    description and a same-process probe re-locking its own file succeeds, so a
    thread would prove nothing.
    """
    lock = AdvisoryFileLock()
    handle = lock.acquire(Path(path_text))
    Path(ready_name).write_text("held" if handle is not None else "failed")
    time.sleep(hold_seconds)
    if handle is not None:
        lock.release(handle)


class TestAdvisoryFileLockProbe(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)
        self.lock = AdvisoryFileLock()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_a_missing_lock_file_is_not_held(self) -> None:
        assert self.lock.is_held(self.base / "absent") is False

    def test_an_unheld_lock_file_is_not_held(self) -> None:
        path = self.base / "pirn-lock"
        path.write_text("")
        assert self.lock.is_held(path) is False

    def test_a_lock_held_by_a_live_process_reads_as_held(self) -> None:
        if not AdvisoryFileLock.platform_supported():
            self.skipTest("no advisory-lock primitive on this interpreter")
        path = self.base / "pirn-lock"
        ready = self.base / "ready"
        holder = multiprocessing.get_context("spawn").Process(
            target=_hold_lock, args=(str(path), str(ready), 5.0)
        )
        holder.start()
        try:
            deadline = time.time() + 10.0
            while not ready.exists() and time.time() < deadline:
                time.sleep(0.02)
            assert ready.read_text() == "held"
            assert self.lock.is_held(path) is True
        finally:
            holder.terminate()
            holder.join(timeout=10.0)

    def test_a_lock_released_by_its_holder_reads_as_free(self) -> None:
        path = self.base / "pirn-lock"
        handle = self.lock.acquire(path)
        assert handle is not None
        self.lock.release(handle)
        assert self.lock.is_held(path) is False

    def test_release_is_idempotent(self) -> None:
        path = self.base / "pirn-lock"
        handle = self.lock.acquire(path)
        assert handle is not None
        self.lock.release(handle)
        self.lock.release(handle)  # must not raise

    def test_an_unopenable_lock_file_reads_as_held(self) -> None:
        """``OSError`` on the probe used to read as "free", i.e. "safe to delete"."""
        path = self.base / "pirn-lock"
        path.write_text("")
        path.chmod(0o000)
        try:
            if self.lock.is_held(path) is False:
                self.skipTest("running as a user for whom chmod 000 does not deny access")
        finally:
            path.chmod(0o600)

    def test_no_locking_primitive_reads_as_held(self) -> None:
        """On an interpreter with neither fcntl nor msvcrt, nothing can be proven free."""
        path = self.base / "pirn-lock"
        path.write_text("")

        class _Unsupported(AdvisoryFileLock):
            @staticmethod
            def platform_supported() -> bool:
                return False

        assert _Unsupported().is_held(path) is True

    def test_no_locking_primitive_declines_to_acquire(self) -> None:
        class _Unsupported(AdvisoryFileLock):
            @staticmethod
            def platform_supported() -> bool:
                return False

        assert _Unsupported().acquire(self.base / "pirn-lock") is None
