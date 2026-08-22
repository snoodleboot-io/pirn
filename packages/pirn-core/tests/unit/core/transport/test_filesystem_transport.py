"""Unit tests for :class:`FilesystemTransport`."""

from __future__ import annotations

import json
import os
import time
import unittest
import unittest.mock
from pathlib import Path

from pirn.core.transport.filesystem_transport import FilesystemTransport
from pirn.core.transport.transport_error import TransportError
from pirn.core.transport.transport_handle import TransportHandle


class TestFilesystemTransport(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _transport(self, **kwargs: object) -> FilesystemTransport:
        return FilesystemTransport(base_dir=self.base, sweep_on_startup=False, **kwargs)

    # --- transport_id ---

    async def test_transport_id_contains_base_dir(self) -> None:
        t = self._transport()
        assert str(self.base) in t.transport_id

    # --- begin_run / run directory ---

    async def test_begin_run_creates_run_directory(self) -> None:
        t = self._transport()
        await t.begin_run("run-1")
        run_dir = self.base / "pirn-run-1"
        assert run_dir.is_dir()
        await t.end_run("run-1", success=True)

    async def test_begin_run_writes_manifest(self) -> None:
        t = self._transport()
        before = time.time()
        await t.begin_run("run-2")
        manifest_path = self.base / "pirn-run-2" / "pirn-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["run_id"] == "run-2"
        assert manifest["created_at"] >= before
        await t.end_run("run-2", success=True)

    # --- write / read ---

    async def test_write_returns_handle(self) -> None:
        t = self._transport()
        await t.begin_run("run-3")
        handle = await t.write("run-3", "knot-a", {"x": 1})
        assert isinstance(handle, TransportHandle)
        assert "filesystem" in handle.transport_id
        await t.end_run("run-3", success=True)

    async def test_read_round_trips_dict(self) -> None:
        t = self._transport()
        await t.begin_run("run-4")
        value = {"patient": "P1", "score": 0.9}
        handle = await t.write("run-4", "scorer", value)
        result = await t.read(handle)
        assert result == value
        await t.end_run("run-4", success=True)

    async def test_read_round_trips_list(self) -> None:
        t = self._transport()
        await t.begin_run("run-5")
        value = [1, 2, 3, 4]
        handle = await t.write("run-5", "knot-b", value)
        result = await t.read(handle)
        assert result == value
        await t.end_run("run-5", success=True)

    async def test_handle_size_bytes_is_positive(self) -> None:
        t = self._transport()
        await t.begin_run("run-6")
        handle = await t.write("run-6", "k", {"a": 1})
        assert handle.size_bytes > 0
        await t.end_run("run-6", success=True)

    async def test_handle_checksum_is_set(self) -> None:
        t = self._transport()
        await t.begin_run("run-7")
        handle = await t.write("run-7", "k", {"a": 1})
        assert handle.checksum != ""
        await t.end_run("run-7", success=True)

    # --- exists ---

    async def test_exists_true_after_write(self) -> None:
        t = self._transport()
        await t.begin_run("run-8")
        handle = await t.write("run-8", "k", {"a": 1})
        assert await t.exists(handle)
        await t.end_run("run-8", success=True)

    async def test_exists_false_for_missing_path(self) -> None:
        t = self._transport()
        handle = TransportHandle(
            transport_id=t.transport_id,
            key=str(self.base / "pirn-ghost" / "no-file.bin"),
            type_name="builtins.dict",
        )
        assert not await t.exists(handle)

    # --- end_run cleanup ---

    async def test_end_run_removes_run_directory(self) -> None:
        t = self._transport()
        await t.begin_run("run-9")
        run_dir = self.base / "pirn-run-9"
        assert run_dir.is_dir()
        await t.end_run("run-9", success=True)
        assert not run_dir.exists()

    async def test_read_after_end_run_raises_transport_error(self) -> None:
        t = self._transport()
        await t.begin_run("run-10")
        handle = await t.write("run-10", "k", {"a": 1})
        await t.end_run("run-10", success=True)
        with self.assertRaises(TransportError):
            await t.read(handle)

    # --- disk space guard ---

    async def test_min_free_gb_zero_does_not_raise(self) -> None:
        t = self._transport(min_free_gb=0.0)
        await t.begin_run("run-disk")
        await t.end_run("run-disk", success=True)

    async def test_min_free_gb_enormous_raises_transport_error(self) -> None:
        t = self._transport(min_free_gb=999_999.0)
        with self.assertRaises(TransportError):
            await t.begin_run("run-no-space")

    # --- sweep_abandoned ---

    async def test_sweep_abandoned_removes_old_unlocked_dirs(self) -> None:
        t = self._transport()
        run_dir = self.base / "pirn-stale"
        run_dir.mkdir()
        old_ts = time.time() - 100 * 3600
        (run_dir / "pirn-manifest.json").write_text(
            json.dumps({"run_id": "stale", "created_at": old_ts})
        )
        removed = t.sweep_abandoned(max_age_hours=48)
        assert removed == 1
        assert not run_dir.exists()

    async def test_sweep_abandoned_skips_fresh_dirs(self) -> None:
        t = self._transport()
        run_dir = self.base / "pirn-fresh"
        run_dir.mkdir()
        (run_dir / "pirn-manifest.json").write_text(
            json.dumps({"run_id": "fresh", "created_at": time.time()})
        )
        removed = t.sweep_abandoned(max_age_hours=48)
        assert removed == 0
        assert run_dir.exists()

    async def test_sweep_abandoned_skips_dirs_without_manifest(self) -> None:
        t = self._transport()
        run_dir = self.base / "pirn-nomanifest"
        run_dir.mkdir()
        removed = t.sweep_abandoned(max_age_hours=0)
        assert removed == 0
        assert run_dir.exists()

    async def test_sweep_on_startup_runs_once(self) -> None:
        stale_dir = self.base / "pirn-stale2"
        stale_dir.mkdir()
        old_ts = time.time() - 100 * 3600
        (stale_dir / "pirn-manifest.json").write_text(
            json.dumps({"run_id": "stale2", "created_at": old_ts})
        )
        t = FilesystemTransport(base_dir=self.base, sweep_on_startup=True)
        await t.begin_run("run-sweep")
        assert not stale_dir.exists()
        await t.end_run("run-sweep", success=True)


class TestFilesystemTransportAtomicWrite(unittest.IsolatedAsyncioTestCase):
    """Outputs land atomically (PIR-805).

    A bare ``write_bytes`` creates the file and then fills it, so a concurrent
    reader can observe a truncated object. Filenames embed a content hash, so
    racing writers write identical bytes and there is no signing layer to
    mistranslate a torn read into a tampering alert — but the torn read is real
    regardless, which is what this pins.
    """

    def setUp(self) -> None:
        import tempfile

        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _transport(self) -> FilesystemTransport:
        return FilesystemTransport(base_dir=self.base, sweep_on_startup=False)

    @unittest.skipUnless(os.name == "posix", "inode identity is only meaningful on POSIX")
    async def test_rewrite_swaps_inode_instead_of_filling_in_place(self) -> None:
        # os.replace installs a NEW inode at the destination; writing in place
        # keeps the original. This pins the mechanism, not just the outcome.
        t = self._transport()
        await t.begin_run("run-atomic")
        handle = await t.write("run-atomic", "knot-a", {"x": 1})
        path = Path(handle.key)
        first_inode = path.stat().st_ino

        # Same knot and same value -> same content hash -> same destination.
        again = await t.write("run-atomic", "knot-a", {"x": 1})

        assert Path(again.key) == path
        assert path.stat().st_ino != first_inode

    async def test_no_temp_file_survives_a_successful_write(self) -> None:
        t = self._transport()
        await t.begin_run("run-clean")
        await t.write("run-clean", "knot-a", {"x": 1})
        assert [p for p in self.base.rglob("*.tmp") if p.is_file()] == []

    async def test_a_failed_write_leaves_no_temp_file_behind(self) -> None:
        # The `except BaseException: unlink; raise` arm — a half-written temp
        # file must not accumulate in the run directory.
        t = self._transport()
        await t.begin_run("run-boom")
        run_dir = self.base / "pirn-run-boom"
        target = run_dir / "victim.bin"

        with unittest.mock.patch("os.replace", side_effect=OSError("no space")):
            with self.assertRaises(OSError):
                FilesystemTransport._write_atomic(target, b"payload")

        assert [p for p in run_dir.rglob("*.tmp") if p.is_file()] == []
        assert not target.exists()

    @unittest.skipUnless(os.name == "posix", "permission bits are POSIX-only")
    async def test_written_file_is_not_tightened_to_0o600(self) -> None:
        # tempfile.mkstemp would force 0o600 here; os.open(..., 0o666) keeps
        # whatever the process umask would have produced for open(path, "wb").
        t = self._transport()
        await t.begin_run("run-perm")
        handle = await t.write("run-perm", "knot-a", {"x": 1})

        expected = 0o666 & ~_current_umask()
        assert Path(handle.key).stat().st_mode & 0o777 == expected


def _current_umask() -> int:
    """Read the process umask without leaving it changed."""
    value = os.umask(0)
    os.umask(value)
    return value
