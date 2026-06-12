#!/usr/bin/env python3
"""Import-graph gate for ``pirn-core`` (SCD-07, constraint C2 / ADR-1, ADR-2).

Two independent checks, both run by default:

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

Exit status is non-zero if either check finds a violation.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
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
        return [
            "could not import pirn to probe backend imports:\n"
            + result.stderr.strip()
        ]
    leaked = [line for line in result.stdout.splitlines() if line.strip()]
    return [
        f"backend package {name!r} was imported at `import pirn` time — "
        "it must import lazily, not at module top level (ADR-2)"
        for name in leaked
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        type=Path,
        default=Path("packages/pirn-core/src/pirn"),
        help="core source tree to scan for the sink check",
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
    args = parser.parse_args()

    run_sink = args.core_is_sink or not args.no_backend_at_core_import
    run_backend = args.no_backend_at_core_import or not args.core_is_sink

    violations: list[str] = []
    if run_sink:
        violations.extend(check_core_is_sink(args.src))
    if run_backend:
        violations.extend(check_no_backend_at_import())

    for v in violations:
        print(v)
    if violations:
        print(f"\nimport-graph gate FAILED: {len(violations)} violation(s)")
        return 1
    print("import-graph gate OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
