"""``FilesystemTransport`` — local-disk transport with run-scoped cleanup.

Each execution run gets an isolated directory under *base_dir*:

    {base_dir}/pirn-{run_id}/
        {knot_id}-{content_hash}.bin
        pirn-manifest.json
        pirn-lock               ← advisory lock held for the run's lifetime

On normal completion (success or failure with clean shutdown) the
executor calls :meth:`end_run` which deletes the directory. On
abnormal termination (SIGKILL, OOM) the directory is left behind and
cleaned up by :meth:`sweep_abandoned` which:

1. Ignores directories whose ``pirn-lock`` file is held by a live process
   (uses ``fcntl`` advisory locking on Linux/macOS; skips lock check on
   other platforms).
2. Deletes directories whose lock file is stale and whose manifest
   timestamp is older than *max_age_hours*.

Startup sweep
-------------
If *sweep_on_startup* is True (the default), :meth:`sweep_abandoned` is
called once during :meth:`begin_run` of the first run. This clears
debris left by a previously crashed process without requiring a separate
maintenance job.

Disk-space guard
----------------
If *min_free_gb* is set, :meth:`begin_run` raises ``TransportError``
immediately if the available space on the *base_dir* volume falls below
the threshold. Fail fast rather than fail mid-run.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

from pirn.core.transport.data_transport import DataTransport
from pirn.core.transport.serializers.serializer_registry import SerializerRegistry
from pirn.core.transport.transport_error import TransportError
from pirn.core.transport.transport_handle import TransportHandle

_log = logging.getLogger(__name__)


class FilesystemTransport(DataTransport):
    """Store knot outputs as files under a local directory.

    Parameters
    ----------
    base_dir:
        Root directory under which per-run subdirectories are created.
        The directory is created if it does not exist.
    max_age_hours:
        Abandoned run directories older than this are deleted by
        :meth:`sweep_abandoned`. Defaults to 48 hours.
    min_free_gb:
        If set, :meth:`begin_run` raises :class:`TransportError` when
        the available disk space on the *base_dir* volume is below this
        threshold.
    sweep_on_startup:
        If True (default), sweep abandoned directories before the first
        run begins.
    serializer_registry:
        Registry of type→serialiser mappings. Defaults to
        :meth:`~pirn.core.transport.serializers.serializer_registry.SerializerRegistry.default`.
    """

    _manifest_name = "pirn-manifest.json"
    _lock_name = "pirn-lock"

    def __init__(
        self,
        *,
        base_dir: str | os.PathLike[str],
        max_age_hours: int = 48,
        min_free_gb: float | None = None,
        sweep_on_startup: bool = True,
        serializer_registry: SerializerRegistry | None = None,
    ) -> None:
        self._base_dir = Path(base_dir)
        self._max_age_hours = max_age_hours
        self._min_free_gb = min_free_gb
        self._sweep_on_startup = sweep_on_startup
        self._registry = serializer_registry or SerializerRegistry.default()
        self._startup_swept = False
        self._lock_handles: dict[str, Any] = {}

    @property
    def transport_id(self) -> str:
        return f"filesystem:{self._base_dir}"

    async def begin_run(self, run_id: str) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        if self._min_free_gb is not None:
            self._check_disk_space()
        if self._sweep_on_startup and not self._startup_swept:
            self._startup_swept = True
            await asyncio.get_event_loop().run_in_executor(None, self.sweep_abandoned)
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        self._write_manifest(run_dir, run_id)
        self._acquire_lock(run_id, run_dir)

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        run_dir = self._run_dir(run_id)
        serialiser = self._registry.get(value)
        try:
            raw = serialiser.serialise(value)
        except Exception as exc:
            raise TransportError(
                f"FilesystemTransport: failed to serialise output of knot {knot_id!r}: {exc}"
            ) from exc
        content_hash = hashlib.sha256(raw).hexdigest()[:16]
        safe_knot_id = knot_id.replace("/", "_").replace(":", "_")
        filename = f"{safe_knot_id}-{content_hash}.bin"
        file_path = run_dir / filename
        try:
            file_path.write_bytes(raw)
        except OSError as exc:
            raise TransportError(
                f"FilesystemTransport: failed to write output of knot {knot_id!r} "
                f"to {file_path}: {exc}"
            ) from exc
        type_name = f"{type(value).__module__}.{type(value).__qualname__}"
        return TransportHandle(
            transport_id=self.transport_id,
            key=str(file_path),
            type_name=type_name,
            size_bytes=len(raw),
            checksum=content_hash,
        )

    async def read(self, handle: TransportHandle) -> Any:
        file_path = Path(handle.key)
        if not file_path.exists():
            raise TransportError(
                f"FilesystemTransport: value for handle key {handle.key!r} not found. "
                "The file may have been swept or the run directory deleted."
            )
        try:
            raw = file_path.read_bytes()
        except OSError as exc:
            raise TransportError(f"FilesystemTransport: cannot read {handle.key!r}: {exc}") from exc
        serialiser = self._registry.get_by_type_name(handle.type_name)
        try:
            return serialiser.deserialise(raw, handle.type_name)
        except Exception as exc:
            raise TransportError(
                f"FilesystemTransport: cannot deserialise {handle.type_name} "
                f"from {handle.key!r}: {exc}"
            ) from exc

    async def exists(self, handle: TransportHandle) -> bool:
        return Path(handle.key).exists()

    async def end_run(self, run_id: str, *, success: bool) -> None:
        self._release_lock(run_id)
        run_dir = self._run_dir(run_id)
        if run_dir.exists():
            try:
                shutil.rmtree(run_dir)
            except OSError as exc:
                raise TransportError(
                    f"FilesystemTransport: failed to clean up run directory {run_dir}: {exc}"
                ) from exc

    def sweep_abandoned(self, max_age_hours: int | None = None) -> int:
        """Delete abandoned run directories and return the count removed.

        A directory is considered abandoned when its lock file is not
        held by any live process and its manifest timestamp is older
        than *max_age_hours* (falls back to the instance default).
        """
        age_limit = max_age_hours if max_age_hours is not None else self._max_age_hours
        cutoff = time.time() - age_limit * 3600
        removed = 0
        if not self._base_dir.exists():
            return 0
        for entry in self._base_dir.iterdir():
            if not entry.is_dir() or not entry.name.startswith("pirn-"):
                continue
            manifest_path = entry / self._manifest_name
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            created_at = manifest.get("created_at", 0.0)
            if created_at > cutoff:
                continue
            if self._is_lock_held(entry / self._lock_name):
                continue
            try:
                shutil.rmtree(entry)
                removed += 1
                _log.info("FilesystemTransport: swept abandoned run directory %s", entry)
            except OSError as exc:
                _log.warning("FilesystemTransport: could not sweep %s: %s", entry, exc)
        return removed

    def _run_dir(self, run_id: str) -> Path:
        safe = run_id.replace("/", "_").replace(":", "_")
        return self._base_dir / f"pirn-{safe}"

    def _write_manifest(self, run_dir: Path, run_id: str) -> None:
        manifest = {"run_id": run_id, "created_at": time.time()}
        (run_dir / self._manifest_name).write_text(json.dumps(manifest))

    def _check_disk_space(self) -> None:
        assert self._min_free_gb is not None
        usage = shutil.disk_usage(self._base_dir)
        free_gb = usage.free / (1024**3)
        if free_gb < self._min_free_gb:
            raise TransportError(
                f"FilesystemTransport: insufficient disk space on {self._base_dir}: "
                f"{free_gb:.1f} GB free, {self._min_free_gb} GB required."
            )

    def _acquire_lock(self, run_id: str, run_dir: Path) -> None:
        lock_path = run_dir / self._lock_name
        try:
            fh = open(lock_path, "w")
            try:
                import fcntl

                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except ImportError:
                pass  # Windows — skip advisory locking
            self._lock_handles[run_id] = fh
        except OSError as exc:
            _log.warning("FilesystemTransport: could not acquire lock for run %s: %s", run_id, exc)

    def _release_lock(self, run_id: str) -> None:
        fh = self._lock_handles.pop(run_id, None)
        if fh is None:
            return
        try:
            import fcntl

            fcntl.flock(fh, fcntl.LOCK_UN)
        except ImportError:
            pass
        try:
            fh.close()
        except OSError:
            pass

    @staticmethod
    def _is_lock_held(lock_path: Path) -> bool:
        if not lock_path.exists():
            return False
        try:
            import fcntl

            with open(lock_path) as fh:
                try:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fh, fcntl.LOCK_UN)
                    return False
                except OSError:
                    return True
        except ImportError:
            return False
        except OSError:
            return False
