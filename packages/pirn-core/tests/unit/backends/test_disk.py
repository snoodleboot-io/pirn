"""Tests for LocalDiskDataStore (beyond signing tests in test_data_store_signing.py)."""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import unittest
import unittest.mock
from pathlib import Path

from pirn.backends._signer import _Signer
from pirn.backends.disk import LocalDiskDataStore


class TestLocalDiskDataStoreKeyLayout(unittest.TestCase):
    """Object key derivation uses two-char prefix sharding."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)
        self.store = LocalDiskDataStore(self.root, allow_unsigned=True)

    def test_object_key_strips_sha256_prefix(self) -> None:
        key = self.store._object_key("sha256:abcdef1234")
        self.assertNotIn("sha256:", key)

    def test_object_key_uses_two_char_prefix_dir(self) -> None:
        key = self.store._object_key("sha256:abcdef1234")
        path = Path(key)
        # Parent dir name should be first 2 chars of clean hash
        self.assertEqual(path.parent.name, "ab")

    def test_object_key_short_hash_uses_underscore(self) -> None:
        key = self.store._object_key("x")
        path = Path(key)
        self.assertEqual(path.parent.name, "_")

    def test_object_key_without_prefix(self) -> None:
        key = self.store._object_key("abcdef12")
        self.assertIn("ab", key)

    def test_root_created_on_init(self) -> None:
        new_root = self.root / "nested" / "dir"
        _ = LocalDiskDataStore(new_root, allow_unsigned=True)
        self.assertTrue(new_root.exists())


class TestLocalDiskDataStoreCRUD(unittest.IsolatedAsyncioTestCase):
    """put / get / has / scrub on real filesystem."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.store = LocalDiskDataStore(Path(self.td.name), allow_unsigned=True)

    async def test_put_then_get_round_trip(self) -> None:
        await self.store.put("sha256:abc123", [1, 2, 3])
        result = await self.store.get("sha256:abc123")
        self.assertEqual(result, [1, 2, 3])

    async def test_has_false_before_put(self) -> None:
        self.assertFalse(await self.store.has("sha256:nothere"))

    async def test_has_true_after_put(self) -> None:
        await self.store.put("sha256:x", 99)
        self.assertTrue(await self.store.has("sha256:x"))

    async def test_scrub_removes_file(self) -> None:
        await self.store.put("sha256:x", "hello")
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))

    async def test_scrub_missing_is_idempotent(self) -> None:
        await self.store.scrub("sha256:nonexistent")

    async def test_get_missing_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            await self.store.get("sha256:missing")

    async def test_file_written_to_disk(self) -> None:
        await self.store.put("sha256:abcdef", 42)
        key_path = Path(self.store._object_key("sha256:abcdef"))
        self.assertTrue(key_path.exists())

    async def test_put_creates_parent_directory(self) -> None:
        await self.store.put("sha256:abcdef", "val")
        key_path = Path(self.store._object_key("sha256:abcdef"))
        self.assertTrue(key_path.parent.exists())

    async def test_stores_complex_object(self) -> None:
        obj = {"nested": {"a": 1}, "list": [True, None, 3.14]}
        await self.store.put("sha256:complex", obj)
        result = await self.store.get("sha256:complex")
        self.assertEqual(result, obj)


class TestLocalDiskDataStoreAtomicWrite(unittest.IsolatedAsyncioTestCase):
    """Writes land atomically (PIR-804).

    An in-place ``truncate + write`` lets a concurrent reader see a
    half-written file, which the signing layer reports as a signature
    mismatch — i.e. a write race that looks like tampering.
    """

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)
        self.store = LocalDiskDataStore(self.root, allow_unsigned=True)

    def __temp_files(self) -> list[Path]:
        return [p for p in self.root.rglob("*.tmp") if p.is_file()]

    @unittest.skipUnless(os.name == "posix", "inode identity is only meaningful on POSIX")
    async def test_rewrite_swaps_inode_instead_of_truncating_in_place(self) -> None:
        # os.replace installs a new inode at the destination.  Writing in
        # place keeps the original inode, so this pins the atomic mechanism.
        await self.store.put("sha256:abc123", "first")
        path = Path(self.store._object_key("sha256:abc123"))
        first_inode = path.stat().st_ino

        await self.store.put("sha256:abc123", "second")

        self.assertNotEqual(first_inode, path.stat().st_ino)
        self.assertEqual(await self.store.get("sha256:abc123"), "second")

    async def test_concurrent_reader_never_observes_torn_payload(self) -> None:
        # The reported symptom: a reader racing a rewrite gets a ValueError
        # from signature verification because it read a partial file.
        store = LocalDiskDataStore(self.root, signer=_Signer.test_signer())
        content_hash = "sha256:" + "a" * 64
        await store.put(content_hash, b"x" * 1024)

        failures: list[str] = []
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                try:
                    asyncio.run(store.get(content_hash))
                except KeyError:
                    pass
                except Exception as exc:  # any read failure is the defect under test
                    failures.append(f"{type(exc).__name__}: {exc}")
                    return

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        try:
            for filler in (b"y", b"z", b"w"):
                await store.put(content_hash, filler * (8 * 1024 * 1024))
        finally:
            stop.set()
            thread.join(timeout=30)

        self.assertEqual(failures, [])

    async def test_successful_write_leaves_no_temp_files(self) -> None:
        await self.store.put("sha256:abc123", "value")
        self.assertEqual(self.__temp_files(), [])

    async def test_failed_write_preserves_previous_value(self) -> None:
        await self.store.put("sha256:abc123", "original")

        with unittest.mock.patch(
            "pirn.backends.disk.os.replace", side_effect=OSError("rename failed")
        ):
            with self.assertRaises(OSError):
                await self.store.put("sha256:abc123", "replacement")

        self.assertEqual(await self.store.get("sha256:abc123"), "original")

    async def test_failed_write_cleans_up_temp_file(self) -> None:
        with unittest.mock.patch(
            "pirn.backends.disk.os.replace", side_effect=OSError("rename failed")
        ):
            with self.assertRaises(OSError):
                await self.store.put("sha256:abc123", "replacement")

        self.assertEqual(self.__temp_files(), [])

    @unittest.skipUnless(os.name == "posix", "POSIX file modes")
    async def test_rewrite_preserves_destination_permissions(self) -> None:
        # os.replace swaps the inode, so the destination's mode must be
        # carried over rather than reset to the temp file's.
        await self.store.put("sha256:abc123", "first")
        path = Path(self.store._object_key("sha256:abc123"))
        path.chmod(0o640)

        await self.store.put("sha256:abc123", "second")

        self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    @unittest.skipUnless(os.name == "posix", "POSIX file modes")
    async def test_new_file_mode_follows_process_umask(self) -> None:
        # Going through a temp file must not silently tighten permissions the
        # way tempfile.mkstemp (0o600) would: a fresh value file still gets
        # 0o666 masked by the umask, exactly as an in-place write produced.
        previous = os.umask(0o027)
        self.addCleanup(os.umask, previous)
        store = LocalDiskDataStore(self.root / "umask", allow_unsigned=True)

        await store.put("sha256:abc123", "value")

        path = Path(store._object_key("sha256:abc123"))
        self.assertEqual(path.stat().st_mode & 0o777, 0o666 & ~0o027)

    async def test_put_still_creates_missing_parent_directories(self) -> None:
        store = LocalDiskDataStore(self.root / "deeper" / "nest", allow_unsigned=True)
        await store.put("sha256:abc123", "value")
        self.assertEqual(await store.get("sha256:abc123"), "value")


class TestLocalDiskDataStoreDeleteIsIdempotent(unittest.IsolatedAsyncioTestCase):
    """`_delete_key` must be a no-op on an absent key (PIR-805).

    The old body was ``if path.exists(): path.unlink()``. Two concurrent
    ``scrub()`` calls can both pass that check, and the loser then raises
    ``FileNotFoundError`` — breaking the base contract, and doing so only
    under concurrency, which is the worst way to find out.
    """

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.store = LocalDiskDataStore(Path(self.td.name), allow_unsigned=True)

    async def test_deleting_an_absent_key_does_not_raise(self) -> None:
        await self.store._delete_key(self.store._object_key("sha256:never-written"))

    async def test_deleting_the_same_key_twice_does_not_raise(self) -> None:
        await self.store.put("sha256:abc123", "value")
        key = self.store._object_key("sha256:abc123")
        await self.store._delete_key(key)
        await self.store._delete_key(key)

    async def test_losing_the_exists_race_does_not_raise(self) -> None:
        # The actual defect, made deterministic.
        #
        # Plain concurrent deletes do NOT reproduce it: the window between
        # `exists()` and `unlink()` is far too narrow to hit reliably, so a
        # gather() of 8 deletes passes against the broken code too and pins
        # nothing. What the old body did wrong is fail when the file vanishes
        # *after* the check — so force exactly that state.
        await self.store.put("sha256:abc123", "value")
        key = self.store._object_key("sha256:abc123")
        Path(key).unlink()  # the winner already deleted it

        with unittest.mock.patch.object(Path, "exists", return_value=True):
            await self.store._delete_key(key)

    async def test_concurrent_deletes_of_one_key_all_succeed(self) -> None:
        # Weaker than the test above — it does not reliably hit the window —
        # but it is the shape a caller actually runs, so it is worth holding.
        await self.store.put("sha256:abc123", "value")
        key = self.store._object_key("sha256:abc123")

        results = await asyncio.gather(
            *(self.store._delete_key(key) for _ in range(8)), return_exceptions=True
        )

        assert [r for r in results if isinstance(r, BaseException)] == []
