"""Scan a folder for pirn tapestries and execution history."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from pirn.viz._tapestry_graph import TapestryGraph


class TapestryGraphScanner:
    """Scan a folder for pirn tapestries and execution history."""

    _builder_names: ClassVar[tuple[str, ...]] = (
        "build_tapestry",
        "build_pipeline",
        "create_tapestry",
        "create_pipeline",
    )

    def scan_folder(self, folder: Path) -> tuple[list[TapestryGraph], list[dict[str, Any]]]:
        """Return (tapestries, runs) found under *folder*."""
        tapestries = self._scan_tapestries(folder)
        runs = self._scan_runs(folder)
        return tapestries, runs

    def _scan_tapestries(self, folder: Path) -> list[TapestryGraph]:
        graphs: list[TapestryGraph] = []
        yaml_paths = sorted(folder.rglob("*.yaml")) + sorted(folder.rglob("*.yml"))
        for path in yaml_paths:
            if self._is_ignored(path):
                continue
            graph = self._scan_yaml(path, folder)
            if graph is not None:
                graphs.append(graph)
        for path in sorted(folder.rglob("*.py")):
            if self._is_ignored(path) or path.name.startswith("_"):
                continue
            graphs.extend(self._scan_python(path, folder))
        return graphs

    def _scan_runs(self, folder: Path) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        for db_path in sorted(folder.rglob("*.db")):
            if self._is_ignored(db_path):
                continue
            runs.extend(self._load_runs_from_db(db_path))
        # Deduplicate by run_id (same db may appear via multiple rglob hits).
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for run in runs:
            if run["run_id"] not in seen:
                seen.add(run["run_id"])
                unique.append(run)
        unique.sort(key=lambda run: run["started_at"], reverse=True)
        return unique

    def _load_runs_from_db(self, db_path: Path, limit: int = 200) -> list[dict[str, Any]]:
        import sqlite3

        try:
            conn = sqlite3.connect(str(db_path))
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "runs" not in tables or "lineage" not in tables:
                conn.close()
                return []

            rows = conn.execute(
                """SELECT run_id, succeeded, started_at, finished_at,
                          dispatcher, actor, trigger,
                          environment_json, runtime_info_json,
                          parent_run_id, parent_knot_id
                   FROM runs
                   ORDER BY started_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            result: list[dict[str, Any]] = []
            for row in rows:
                (
                    run_id,
                    succeeded,
                    started_at,
                    finished_at,
                    dispatcher,
                    actor,
                    trigger,
                    env_json,
                    rt_json,
                    parent_run_id,
                    parent_knot_id,
                ) = row

                duration_ms = self._duration_ms(started_at, finished_at)

                lineage_rows = conn.execute(
                    """SELECT knot_id, knot_class, outcome,
                              started_at, finished_at,
                              error_record_id, skip_reason, output_hash,
                              knot_config_hash, payload_json
                       FROM lineage WHERE run_id = ?""",
                    (run_id,),
                ).fetchall()

                import json as _json

                knots: dict[str, Any] = {}
                for lr in lineage_rows:
                    if lr[0] == "__loop_terminal__":
                        continue
                    (
                        kid,
                        kclass,
                        outcome,
                        k_start,
                        k_end,
                        err_id,
                        skip_reason,
                        output_hash,
                        config_hash,
                        payload_json,
                    ) = lr
                    parent_knot_ids: dict[str, str] = {}
                    extra: dict = {}
                    source_hash: str = ""
                    try:
                        payload = _json.loads(payload_json) if payload_json else {}
                        extra = payload.get("extra", {})
                        parent_knot_ids = extra.get("parent_knot_ids", {})
                        source_hash = payload.get("source_hash") or ""
                    except Exception:
                        pass
                    knots[kid] = {
                        "outcome": outcome,
                        "class": kclass.split(".")[-1],
                        "started_at": str(k_start) if k_start else "",
                        "finished_at": str(k_end) if k_end else "",
                        "duration_ms": self._duration_ms(k_start, k_end),
                        "output_hash": output_hash or "",
                        "knot_config_hash": config_hash or "",
                        "error_record_id": err_id or "",
                        "skip_reason": skip_reason or "",
                        "parent_knot_ids": parent_knot_ids,
                        "source_hash": source_hash,
                        "extra": {k: v for k, v in extra.items() if k != "parent_knot_ids"},
                    }

                # Load exceptions keyed by id from the run payload_json, and
                # extract child_run_ids: {knot_id: run_id} from outputs.
                child_run_ids: dict[str, Any] = {}
                try:
                    run_payload = _json.loads(
                        conn.execute(
                            "SELECT payload_json FROM runs WHERE run_id=?", (run_id,)
                        ).fetchone()[0]
                    )
                    exceptions = {e["id"]: e for e in run_payload.get("exceptions", [])}
                    for knot_id, val in run_payload.get("outputs", {}).items():
                        if isinstance(val, dict) and "run_id" in val:
                            child_run_ids[knot_id] = val["run_id"]
                except Exception:
                    exceptions = {}

                # Also reverse-lookup child runs via parent_run_id / parent_knot_id
                # so SubTapestry nodes that return plain objects (not RunResult) still
                # get drill-down links in the explorer.  Collect all child runs per
                # knot to support loops (multiple _run_inner calls per knot).
                try:
                    child_rows = conn.execute(
                        "SELECT parent_knot_id, run_id FROM runs"
                        " WHERE parent_run_id=? AND parent_knot_id IS NOT NULL"
                        " ORDER BY started_at",
                        (run_id,),
                    ).fetchall()
                    for child_knot_id, child_rid in child_rows:
                        existing = child_run_ids.get(child_knot_id)
                        if existing is None:
                            child_run_ids[child_knot_id] = child_rid
                        elif isinstance(existing, str):
                            child_run_ids[child_knot_id] = [existing, child_rid]
                        else:
                            existing.append(child_rid)
                except Exception:
                    pass

                # Fetch parent_input_hashes per knot from lineage_inputs.
                if "lineage_inputs" in tables:
                    try:
                        li_rows = conn.execute(
                            "SELECT knot_id, input_name, input_hash"
                            " FROM lineage_inputs WHERE run_id = ?",
                            (run_id,),
                        ).fetchall()
                        for kid, input_name, input_hash in li_rows:
                            if kid in knots:
                                pih = knots[kid].setdefault("parent_input_hashes", {})
                                pih[input_name] = input_hash
                    except Exception:
                        pass

                # Collect knot_sources for every source_hash referenced in
                # this run's knots so the UI can render source code modals.
                knot_sources: dict[str, dict] = {}
                if "knot_sources" in tables:
                    hashes = [k["source_hash"] for k in knots.values() if k.get("source_hash")]
                    if hashes:
                        placeholders = ",".join("?" * len(hashes))
                        try:
                            ks_rows = conn.execute(
                                f"SELECT source_hash, source_text, knot_class, pirn_version"
                                f" FROM knot_sources WHERE source_hash IN ({placeholders})",
                                hashes,
                            ).fetchall()
                            for sh, st, kc, pv in ks_rows:
                                knot_sources[sh] = {
                                    "source_text": st,
                                    "knot_class": kc,
                                    "pirn_version": pv,
                                }
                        except Exception:
                            pass

                result.append(
                    {
                        "run_id": run_id,
                        "succeeded": bool(succeeded),
                        "started_at": str(started_at),
                        "finished_at": str(finished_at),
                        "duration_ms": duration_ms,
                        "dispatcher": dispatcher or "",
                        "actor": actor or "",
                        "trigger": trigger or "",
                        "environment": _json.loads(env_json) if env_json else {},
                        "runtime_info": _json.loads(rt_json) if rt_json else {},
                        "knots": knots,
                        "exceptions": exceptions,
                        "parent_run_id": parent_run_id or None,
                        "parent_knot_id": parent_knot_id or None,
                        "child_run_ids": child_run_ids,
                        "knot_sources": knot_sources,
                    }
                )

            conn.close()
            return result
        except Exception:
            return []

    @staticmethod
    def _duration_ms(start: Any, end: Any) -> int:
        try:
            return max(
                0,
                int(
                    (
                        TapestryGraphScanner._parse_iso(end)
                        - TapestryGraphScanner._parse_iso(start)
                    ).total_seconds()
                    * 1000
                ),
            )
        except Exception:
            return 0

    @staticmethod
    def _parse_iso(iso_value: Any) -> datetime:
        iso_str = str(iso_value).replace(" ", "T")
        if iso_str.endswith("+00:00") or iso_str.endswith("Z"):
            iso_str = iso_str.removesuffix("Z").removesuffix("+00:00")
        return datetime.fromisoformat(iso_str).replace(tzinfo=UTC)

    @staticmethod
    def _is_ignored(path: Path) -> bool:
        return any(
            part in {"__pycache__", ".git", ".venv", "node_modules", ".tox"} for part in path.parts
        )

    @staticmethod
    def _knot_description(knot: Any) -> str:
        doc = knot.__class__.__doc__ or ""
        for line in doc.splitlines():
            line = line.strip()
            if line:
                return line
        return ""

    @classmethod
    def _tapestry_to_graph(cls, tapestry: Any, name: str, source: str) -> TapestryGraph:
        from pirn.nodes.sub_tapestry import SubTapestry as _SubTapestry

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for knot in tapestry._store.all():
            nodes.append(
                {
                    "id": knot.knot_id,
                    "class": type(knot).__name__,
                    "description": cls._knot_description(knot),
                    "is_sub_tapestry": isinstance(knot, _SubTapestry),
                }
            )
            for input_name, parent in knot.parents.items():
                edges.append(
                    {"source": parent.knot_id, "target": knot.knot_id, "label": input_name}
                )
        return TapestryGraph(name=name, source=source, nodes=nodes, edges=edges)

    @classmethod
    def _scan_yaml(cls, path: Path, root: Path) -> TapestryGraph | None:
        source = str(path.relative_to(root))
        try:
            import yaml as _yaml

            raw = _yaml.safe_load(path.read_text())
            name = (raw or {}).get("name") or path.stem
            from pirn.yaml_loader.loader import load_pipeline

            tapestry = load_pipeline(path.read_text())
            return cls._tapestry_to_graph(tapestry, name, source)
        except Exception as exc:
            return TapestryGraph(name=path.stem, source=source, error=str(exc))

    @classmethod
    def _scan_python(cls, path: Path, root: Path) -> list[TapestryGraph]:
        source = str(path.relative_to(root))
        results: list[TapestryGraph] = []
        try:
            import sys as _sys

            mod_name = f"_pirn_scan_{path.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                return []
            module = importlib.util.module_from_spec(spec)
            # Register in sys.modules so @dataclass (Python 3.14+) can resolve cls.__module__.
            _sys.modules[mod_name] = module
            try:
                spec.loader.exec_module(module)  # type: ignore[union-attr]
            finally:
                _sys.modules.pop(mod_name, None)

            from pirn.tapestry import Tapestry

            for attr_name in dir(module):
                val = getattr(module, attr_name, None)
                if isinstance(val, Tapestry) and val._store.all():
                    results.append(cls._tapestry_to_graph(val, f"{path.stem}.{attr_name}", source))

            if not results:
                for builder_name in cls._builder_names:
                    fn = getattr(module, builder_name, None)
                    if callable(fn):
                        try:
                            val = fn()
                            if isinstance(val, Tapestry) and val._store.all():
                                results.append(cls._tapestry_to_graph(val, path.stem, source))
                                break
                        except Exception:
                            pass
        except Exception:
            pass
        return results


def scan_folder(folder: Path) -> tuple[list[TapestryGraph], list[dict[str, Any]]]:
    """Public wrapper around :meth:`TapestryGraphScanner.scan_folder`."""
    return TapestryGraphScanner().scan_folder(folder)
