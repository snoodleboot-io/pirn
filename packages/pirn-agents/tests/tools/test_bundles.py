"""Tests for the curated Toolset bundle factories (PIR-236 / PIR-175).

Verifies each factory groups the expected tools with sane defaults and honours
its toggles, and that constructing bundles imports no optional backend.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys

from pirn_agents.tools.bundles import Bundles
from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor
from pirn_agents.tools.sql.sqlite_connector import SqliteConnector
from tests.conftest import StubLLMProvider, StubMemoryStore


def _names(toolset: object) -> set[str]:
    return {tool.name for tool in toolset}


def test_calculator_toolset() -> None:
    assert _names(Bundles.calculator_toolset()) == {"calculator"}


def test_web_toolset_default_and_with_search() -> None:
    assert _names(Bundles.web_toolset()) == {"http_request", "html_to_text"}
    from pirn_agents.tools.web.search_backend import SearchBackend

    class _B(SearchBackend):
        async def search(self, query: str, *, max_results: int):
            return []

    assert _names(Bundles.web_toolset(search_backend=_B())) == {
        "web_search",
        "http_request",
        "html_to_text",
    }


def test_filesystem_toolset(tmp_path) -> None:
    full = _names(Bundles.filesystem_toolset(root=str(tmp_path)))
    assert full == {"read_file", "write_file", "list_dir", "glob"}
    read_only = _names(Bundles.filesystem_toolset(root=str(tmp_path), include_write=False))
    assert "write_file" not in read_only


def test_data_toolset() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    names = _names(Bundles.data_toolset(connector=SqliteConnector(connection=conn)))
    assert names == {"sql_query", "calculator"}
    assert _names(
        Bundles.data_toolset(connector=SqliteConnector(connection=conn), include_calculator=False)
    ) == {"sql_query"}
    conn.close()


def test_retrieval_toolset() -> None:
    store = StubMemoryStore()
    assert _names(Bundles.retrieval_toolset(store=store)) == {"retriever"}
    assert _names(Bundles.retrieval_toolset(store=store, llm=StubLLMProvider(["x"]))) == {
        "retriever",
        "rag",
    }


def test_sandbox_toolset() -> None:
    executor = SandboxExecutor()
    assert _names(Bundles.sandbox_toolset(executor=executor)) == {"python_exec", "shell"}
    assert _names(Bundles.sandbox_toolset(executor=executor, include_shell=False)) == {
        "python_exec"
    }


def test_bundles_import_is_backend_free() -> None:
    # Building bundles must not eagerly import optional backends. Check in a
    # FRESH subprocess: the in-process sys.modules is polluted by other tests
    # (CI installs the extras, so earlier tests import httpx/aiosqlite), which
    # would make an in-process assertion flaky. A clean interpreter isolates
    # exactly what building the bundles imports.
    code = (
        "import sys\n"
        "from pirn_agents.tools.bundles import Bundles\n"
        "Bundles.web_toolset()\n"
        "bad = [m for m in ('httpx', 'aiosqlite') if m in sys.modules]\n"
        "raise SystemExit('bundles eagerly imported: ' + repr(bad) if bad else 0)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
