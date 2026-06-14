#!/usr/bin/env python3
"""Import-graph gate for the pirn workspace (SCD-07 + SCD-10).

Four independent checks, all run by default (pass a ``--*`` selector to run a
subset):

C2 — *core is a sink.*
    No module under ``packages/pirn-core/src/pirn/`` may import a top-level
    domain package (``pirn_signal``, ``pirn_data``, ``pirn_ml``, ``pirn_agents``,
    ``pirn_health``, ``pirn_oilgas``). Core must depend on zero domains.

    (During Phase 1 the six domains still ride along *inside* core's tree as
    ``pirn.domains.*``; those are not top-level ``pirn_<domain>`` packages, so
    they do not — and must not — trip this check. The check guards the
    post-extraction boundary so a stray ``import pirn_data`` can never leak into
    core.)

No-backend-at-import — *core stays dependency-light.*
    Importing ``pirn`` in the current environment must not pull any optional
    connector/backend third-party package (asyncpg, aioboto3, kafka clients,
    zstandard, …) into ``sys.modules``. Backends import their heavy deps lazily
    (method-level / ``try-except`` / ``ExtrasLoader.require()``), so a clean
    ``import pirn`` touches none of them even when they are installed (ADR-2
    contract boundary).

Domain DAG (real imports) — *acyclic, one domain edge.* (SCD-10 / C1 + C3)
    Builds the cross-domain edge set from real ``pirn.domains.<x>`` imports and
    asserts the graph is acyclic and its only domain->domain edge is
    ``ml -> data``. This proves SCD-08 removed ``agents -> ml`` and SCD-09
    removed ``health -> agents``, with ``ml -> data`` (ADR-3) retained.

Package DAG (declared deps) — *acyclic, one domain edge.* (SCD-10 / C1 + C3)
    Parses each package's ``pyproject.toml`` dependencies and asserts the
    inter-package graph is acyclic and its only domain->domain hard edge is
    ``pirn-ml -> pirn-data``. A new domain->domain dependency fails the build
    pending an ADR amendment.

Exit status is non-zero if any check finds a violation.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tomllib
from pathlib import Path

# Top-level domain import names that core must never import (post-extraction).
_domain_packages = (
    "pirn_signal",
    "pirn_data",
    "pirn_ml",
    "pirn_agents",
    "pirn_health",
    "pirn_oilgas",
)

# The six extractable domains (core is the DAG root, not a domain).
_domain_names = (
    "signal",
    "data",
    "ml",
    "agents",
    "health",
    "oilgas",
)

# The sole permitted domain->domain hard edge after Phase 2 (ADR-3 / C3):
# ``ml`` depends on ``data``; ``agents->ml`` (SCD-08) and ``health->agents``
# (SCD-09) are eliminated.
_allowed_domain_edge = ("ml", "data")
_allowed_package_edge = ("pirn-ml", "pirn-data")

# Optional connector/backend + codec third-party packages. None of these may be
# imported as a side effect of ``import pirn``. Names are the *import* names
# (what shows up in ``sys.modules``), not the PyPI distribution names.
_backend_modules = (
    # databases
    "asyncpg",
    "aiosqlite",
    "duckdb",
    "aiomysql",
    "aioodbc",
    "oracledb",
    "snowflake",
    "clickhouse_connect",
    "databricks",
    "google.cloud.bigquery",
    # object storage
    "aioboto3",
    "gcloud_aio_storage",
    "azure.storage.blob",
    # messaging / streaming
    "aiokafka",
    "aio_pika",
    "azure.servicebus",
    "google.cloud.pubsub",
    "glide",  # valkey-glide
    # compression codecs
    "zstandard",
    "snappy",
    "lz4",
)


def _imported_module_roots(tree: ast.AST) -> set[str]:
    """Collect dotted module names referenced by ``import`` / ``from`` stmts."""
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # Absolute imports only; relative (level > 0) can't reach a domain.
            if node.level == 0 and node.module is not None:
                modules.add(node.module)
    return modules


def check_core_is_sink(src: Path) -> list[str]:
    """C2: fail if any file under ``src`` imports a top-level domain package."""
    violations: list[str] = []
    for path in sorted(src.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for module in _imported_module_roots(tree):
            root = module.split(".", 1)[0]
            if root in _domain_packages:
                violations.append(
                    f"{path}: core imports domain package {module!r} — "
                    "core must depend on zero domains (constraint C2)"
                )
    return violations


def check_no_backend_at_import() -> list[str]:
    """Fail if ``import pirn`` pulls any backend package into ``sys.modules``."""
    probe = (
        "import sys\n"
        "import pirn  # noqa: F401\n"
        f"candidates = {list(_backend_modules)!r}\n"
        "leaked = sorted(m for m in candidates if m in sys.modules)\n"
        "print('\\n'.join(leaked))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ["could not import pirn to probe backend imports:\n" + result.stderr.strip()]
    leaked = [line for line in result.stdout.splitlines() if line.strip()]
    return [
        f"backend package {name!r} was imported at `import pirn` time — "
        "it must import lazily, not at module top level (ADR-2)"
        for name in leaked
    ]


def _find_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    """Return a node cycle (as a path) if the directed graph has one, else None.

    Plain DFS three-colouring — keeps the gate stdlib-only (no networkx).
    """
    white, gray, black = 0, 1, 2
    color: dict[str, int] = {node: white for node in edges}
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = gray
        path.append(node)
        for nxt in sorted(edges.get(node, set())):
            state = color.get(nxt, white)
            if state == gray:
                return [*path[path.index(nxt) :], nxt]
            if state == white:
                found = visit(nxt)
                if found is not None:
                    return found
        path.pop()
        color[node] = black
        return None

    for node in sorted(edges):
        if color[node] == white:
            found = visit(node)
            if found is not None:
                return found
    return None


def check_domain_dag(src: Path) -> list[str]:
    """C1+C3 over *real imports*: domains form an acyclic graph whose only
    domain->domain edge is ``ml -> data``.

    Scans each ``<src>/domains/<domain>/`` subtree for ``pirn.domains.<other>``
    imports and asserts (a) the induced graph is acyclic (C1) and (b) the set of
    cross-domain edges is exactly ``{(ml, data)}`` — i.e. SCD-08 removed the
    ``agents -> ml`` edge and SCD-09 removed the ``health -> agents`` edge, while
    the retained ``ml -> data`` edge (ADR-3) is still present.
    """
    domains_root = src / "domains"
    edges: dict[str, set[str]] = {domain: set() for domain in _domain_names}
    for domain in _domain_names:
        domain_dir = domains_root / domain
        if not domain_dir.is_dir():
            continue
        for path in sorted(domain_dir.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:
                continue
            for module in _imported_module_roots(tree):
                parts = module.split(".")
                if len(parts) >= 3 and parts[0] == "pirn" and parts[1] == "domains":
                    other = parts[2]
                    if other in _domain_names and other != domain:
                        edges[domain].add(other)
    return _dag_violations(
        edges,
        allowed_edge=_allowed_domain_edge,
        kind="domain import graph",
    )


def _distribution_name(spec: str) -> str:
    """Extract the bare distribution name from a PEP 508 dependency string."""
    return re.split(r"[<>=!~;\[\( ]", spec.strip(), maxsplit=1)[0].strip()


def check_package_dag(packages_root: Path) -> list[str]:
    """C1+C3 over *declared deps*: the inter-package graph parsed from each
    ``pyproject.toml`` is acyclic and its only domain->domain hard edge is
    ``pirn-ml -> pirn-data``.

    A new domain->domain dependency declared in any package fails the build
    pending an ADR amendment (ADR-3).
    """
    parsed: dict[str, list[str]] = {}
    for pyproject in sorted(packages_root.glob("*/pyproject.toml")):
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = data.get("project", {})
        name = project.get("name")
        if not name:
            continue
        parsed[name] = project.get("dependencies", [])

    known = set(parsed)
    edges: dict[str, set[str]] = {name: set() for name in parsed}
    for name, deps in parsed.items():
        for spec in deps:
            dep = _distribution_name(spec)
            if dep in known and dep != name:
                edges[name].add(dep)

    domain_pkgs = {f"pirn-{domain}" for domain in _domain_names}
    return _dag_violations(
        edges,
        allowed_edge=_allowed_package_edge,
        kind="declared package dependency graph",
        domain_nodes=domain_pkgs,
    )


def _dag_violations(
    edges: dict[str, set[str]],
    *,
    allowed_edge: tuple[str, str],
    kind: str,
    domain_nodes: set[str] | None = None,
) -> list[str]:
    """Shared acyclicity (C1) + sole-domain-edge (C3) assertions over ``edges``.

    ``domain_nodes`` restricts which endpoints count as "domain->domain"; when
    None every node is treated as a domain (the in-tree import graph case).
    """
    violations: list[str] = []
    cycle = _find_cycle(edges)
    if cycle is not None:
        violations.append(
            f"{kind} has a cycle: "
            + " -> ".join(cycle)
            + " (constraint C1: the package DAG must be acyclic)"
        )

    def is_domain(node: str) -> bool:
        return domain_nodes is None or node in domain_nodes

    cross = {
        (src, dst)
        for src, outs in edges.items()
        for dst in outs
        if is_domain(src) and is_domain(dst)
    }
    for src, dst in sorted(cross - {allowed_edge}):
        violations.append(
            f"unexpected domain->domain edge {src!r} -> {dst!r} in the {kind} — "
            f"the only permitted domain edge is {allowed_edge[0]!r} -> "
            f"{allowed_edge[1]!r} (constraint C3 / ADR-3); a new edge requires an "
            "ADR amendment"
        )
    if allowed_edge not in cross:
        violations.append(
            f"retained edge {allowed_edge[0]!r} -> {allowed_edge[1]!r} is missing "
            f"from the {kind} — it must be retained, not broken (ADR-3)"
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        type=Path,
        default=Path("packages/pirn-core/src/pirn"),
        help="core source tree to scan for the sink + domain-DAG checks",
    )
    parser.add_argument(
        "--packages-root",
        type=Path,
        default=Path("packages"),
        help="workspace packages dir for the declared-dependency DAG check",
    )
    parser.add_argument(
        "--core-is-sink",
        action="store_true",
        help="run only the C2 core-is-sink check",
    )
    parser.add_argument(
        "--no-backend-at-core-import",
        action="store_true",
        help="run only the no-backend-at-import check",
    )
    parser.add_argument(
        "--domain-dag",
        action="store_true",
        help="run only the domain import-graph DAG check (C1/C3, SCD-10)",
    )
    parser.add_argument(
        "--package-dag",
        action="store_true",
        help="run only the declared-dependency DAG check (C1/C3, SCD-10)",
    )
    args = parser.parse_args()

    # No selector flag → run every check. Any selector → run only those chosen.
    run_all = not (
        args.core_is_sink or args.no_backend_at_core_import or args.domain_dag or args.package_dag
    )

    violations: list[str] = []
    if run_all or args.core_is_sink:
        violations.extend(check_core_is_sink(args.src))
    if run_all or args.no_backend_at_core_import:
        violations.extend(check_no_backend_at_import())
    if run_all or args.domain_dag:
        violations.extend(check_domain_dag(args.src))
    if run_all or args.package_dag:
        violations.extend(check_package_dag(args.packages_root))

    for v in violations:
        print(v)
    if violations:
        print(f"\nimport-graph gate FAILED: {len(violations)} violation(s)")
        return 1
    print("import-graph gate OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
