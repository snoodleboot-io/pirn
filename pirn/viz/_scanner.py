"""Scan a folder for pirn tapestries and execution history."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TapestryGraph:
    name: str
    source: str
    nodes: list[dict[str, str]] = field(default_factory=list)
    edges: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "nodes": self.nodes,
            "edges": self.edges,
            "error": self.error,
        }


def scan_folder(folder: Path) -> tuple[list[TapestryGraph], list[dict[str, Any]]]:
    """Return (tapestries, runs) found under *folder*."""
    tapestries = _scan_tapestries(folder)
    runs = _scan_runs(folder)
    return tapestries, runs


def _scan_tapestries(folder: Path) -> list[TapestryGraph]:
    graphs: list[TapestryGraph] = []
    yaml_paths = sorted(folder.rglob("*.yaml")) + sorted(folder.rglob("*.yml"))
    for path in yaml_paths:
        if _is_ignored(path):
            continue
        g = _scan_yaml(path, folder)
        if g is not None:
            graphs.append(g)
    for path in sorted(folder.rglob("*.py")):
        if _is_ignored(path) or path.name.startswith("_"):
            continue
        graphs.extend(_scan_python(path, folder))
    return graphs


def _scan_runs(folder: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for db_path in sorted(folder.rglob("*.db")):
        if _is_ignored(db_path):
            continue
        runs.extend(_load_runs_from_db(db_path))
    # Deduplicate by run_id (same db may appear via multiple rglob hits).
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in runs:
        if r["run_id"] not in seen:
            seen.add(r["run_id"])
            unique.append(r)
    unique.sort(key=lambda r: r["started_at"], reverse=True)
    return unique


def _load_runs_from_db(db_path: Path, limit: int = 200) -> list[dict[str, Any]]:
    import sqlite3
    try:
        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "runs" not in tables or "lineage" not in tables:
            conn.close()
            return []

        rows = conn.execute(
            """SELECT run_id, succeeded, started_at, finished_at,
                      dispatcher, actor, trigger,
                      environment_json, runtime_info_json
               FROM runs
               ORDER BY started_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            (run_id, succeeded, started_at, finished_at,
             dispatcher, actor, trigger, env_json, rt_json) = row

            duration_ms = _duration_ms(started_at, finished_at)

            lineage_rows = conn.execute(
                """SELECT knot_id, knot_class, outcome,
                          started_at, finished_at,
                          error_record_id, skip_reason, output_hash,
                          knot_config_hash
                   FROM lineage WHERE run_id = ?""",
                (run_id,),
            ).fetchall()

            knots: dict[str, Any] = {}
            for lr in lineage_rows:
                (kid, kclass, outcome,
                 k_start, k_end,
                 err_id, skip_reason, output_hash,
                 config_hash) = lr
                knots[kid] = {
                    "outcome": outcome,
                    "class": kclass.split(".")[-1],
                    "started_at": str(k_start) if k_start else "",
                    "finished_at": str(k_end) if k_end else "",
                    "duration_ms": _duration_ms(k_start, k_end),
                    "output_hash": output_hash or "",
                    "knot_config_hash": config_hash or "",
                    "error_record_id": err_id or "",
                    "skip_reason": skip_reason or "",
                }

            import json as _json
            # Load exceptions keyed by id from the run payload_json
            try:
                run_payload = _json.loads(conn.execute(
                    "SELECT payload_json FROM runs WHERE run_id=?", (run_id,)
                ).fetchone()[0])
                exceptions = {e["id"]: e for e in run_payload.get("exceptions", [])}
            except Exception:
                exceptions = {}

            result.append({
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
            })

        conn.close()
        return result
    except Exception:
        return []


def _duration_ms(start: Any, end: Any) -> int:
    try:
        def _parse(s: Any) -> datetime:
            s = str(s).replace(" ", "T")
            if s.endswith("+00:00") or s.endswith("Z"):
                s = s.rstrip("Z").rstrip("+00:00")
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        return max(0, int((_parse(end) - _parse(start)).total_seconds() * 1000))
    except Exception:
        return 0


def _is_ignored(path: Path) -> bool:
    return any(
        part in {"__pycache__", ".git", ".venv", "node_modules", ".tox"}
        for part in path.parts
    )


def _knot_description(knot: Any) -> str:
    doc = knot.__class__.__doc__ or ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _tapestry_to_graph(tapestry: Any, name: str, source: str) -> TapestryGraph:
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    for knot in tapestry._store.all():
        nodes.append({
            "id": knot.knot_id,
            "class": type(knot).__name__,
            "description": _knot_description(knot),
        })
        for input_name, parent in knot.parents.items():
            edges.append({"source": parent.knot_id, "target": knot.knot_id, "label": input_name})
    return TapestryGraph(name=name, source=source, nodes=nodes, edges=edges)


def _scan_yaml(path: Path, root: Path) -> TapestryGraph | None:
    name = path.stem
    source = str(path.relative_to(root))
    try:
        from pirn.yaml_loader.loader import load_pipeline
        tapestry = load_pipeline(str(path))
        return _tapestry_to_graph(tapestry, name, source)
    except Exception as exc:
        return TapestryGraph(name=name, source=source, error=str(exc))


_BUILDER_NAMES = ("build_tapestry", "build_pipeline", "create_tapestry", "create_pipeline")


def _scan_python(path: Path, root: Path) -> list[TapestryGraph]:
    source = str(path.relative_to(root))
    results: list[TapestryGraph] = []
    try:
        spec = importlib.util.spec_from_file_location(f"_pirn_scan_{path.stem}", path)
        if spec is None or spec.loader is None:
            return []
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        from pirn.tapestry import Tapestry

        for attr_name in dir(module):
            val = getattr(module, attr_name, None)
            if isinstance(val, Tapestry) and val._store.all():
                results.append(_tapestry_to_graph(val, f"{path.stem}.{attr_name}", source))

        if not results:
            for builder_name in _BUILDER_NAMES:
                fn = getattr(module, builder_name, None)
                if callable(fn):
                    try:
                        val = fn()
                        if isinstance(val, Tapestry) and val._store.all():
                            results.append(_tapestry_to_graph(val, path.stem, source))
                            break
                    except Exception:
                        pass
    except Exception:
        pass
    return results
