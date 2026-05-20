from __future__ import annotations

import importlib.metadata
import socket
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot_source import KnotSourceRecord
from pirn.core.lineage import KnotLineage
from pirn.core.run_result import RunResult
from pirn.managers.exception_manager import ExceptionManager
from pirn.managers.status_manager import StatusManager


class RunContext:
    """Live, run-scoped services carried through the engine."""

    def __init__(
        self,
        run_id: str,
        terminals_requested: list[str],
        dispatcher_name: str,
        parameters: dict[str, Any] | None = None,
        traceback_filter: Callable[[str], str] | None = None,
        actor: str | None = None,
        environment: dict[str, str] | None = None,
        trigger: str | None = None,
        parent_run_id: str | None = None,
        parent_knot_id: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.terminals_requested = terminals_requested
        self.dispatcher_name = dispatcher_name
        self.parameters: dict[str, Any] = parameters or {}
        self.status = StatusManager(run_id)
        self.exceptions = ExceptionManager(run_id, traceback_filter=traceback_filter)
        self.lineage: list[KnotLineage] = []
        self.skipped: list[str] = []
        # Deduplicated source snapshots keyed by source_hash — populated
        # during the run, persisted after finalization.
        self.knot_sources: dict[str, KnotSourceRecord] = {}
        self.started_at = datetime.now(UTC)
        self.parent_run_id = parent_run_id
        self.parent_knot_id = parent_knot_id

        # 7 W's — Who, Where, Why
        self.actor = actor
        self.trigger = trigger
        self.environment: dict[str, str] = {"hostname": socket.gethostname(), **(environment or {})}

        # By What Means — auto-populated at run construction time
        def _pkg_version(name: str) -> str:
            try:
                return importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                return "unknown"

        import cloudpickle

        self.runtime_info: dict[str, str] = {
            "python_version": sys.version,
            "pirn_version": _pkg_version("pirn"),
            "cloudpickle_version": _pkg_version("cloudpickle"),
            "cloudpickle_pickle_protocol": str(cloudpickle.DEFAULT_PROTOCOL),
            "platform": sys.platform,
            "vcs_commit": self._resolve_vcs_commit(),
        }

    @staticmethod
    def _resolve_vcs_commit() -> str:
        """Return the HEAD git SHA of the calling project, or empty string."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def add_lineage(self, record: KnotLineage) -> None:
        self.lineage.append(record)

    def add_knot_source(self, record: KnotSourceRecord) -> None:
        self.knot_sources.setdefault(record.source_hash, record)

    def finalize(self, outputs: dict[str, Any]) -> RunResult:
        return RunResult(
            run_id=self.run_id,
            run_path=f"/{self.run_id}",
            parent_run_id=self.parent_run_id,
            parent_knot_id=self.parent_knot_id,
            terminals_requested=self.terminals_requested,
            outputs=outputs,
            skipped=self.skipped,
            exceptions=self.exceptions.report(),
            lineage=list(self.lineage),
            status_events=self.status.events(),
            started_at=self.started_at,
            finished_at=datetime.now(UTC),
            dispatcher=self.dispatcher_name,
            actor=self.actor,
            environment=self.environment,
            trigger=self.trigger,
            runtime_info=self.runtime_info,
        )
