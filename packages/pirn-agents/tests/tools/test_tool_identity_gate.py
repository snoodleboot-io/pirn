"""Gate: every tool that opts in to content identity declares every constructor input.

Opting in through :meth:`Tool.content_identity` is not type-enforced (PIR-840). A tool
that declares ``{"root": ...}`` today and gains a ``follow_symlinks`` argument
tomorrow would silently hash two differently-behaving instances equal, and replay
would serve one's recording to the other. That is the measured hazard this gate
exists for: before PIR-840's design, ``ReadFileTool(root=A)`` was served as
``root=B``.

Two checks:

* **Per-argument variation.** For each opted-in tool, build a baseline, confirm it
  is content-identified and hashes equal when rebuilt (otherwise "the hash changed"
  would be vacuous), then vary each ``__init__`` parameter one at a time and assert
  the hash changes. The parameters covered must equal the introspected signature,
  so a new constructor argument fails here until someone decides what it does to
  identity.
* **Coverage ratchet.** Every class in the workspace (``packages/``, ``examples/``,
  ``scripts/``) that defines ``content_identity`` must have a case below or a named
  exemption — by exact equality, so removing an opt-in without updating the gate
  also fails. The scan is whole-workspace and by AST, not by importing one package,
  because a package-local registry previously missed classes defined elsewhere.
* **Inheritance ratchet.** The opt-in is not inherited (review of PR #310): a
  subclass of an opted-in tool is identity-keyed unless it re-declares
  ``content_identity``. Every such subclass in the workspace must be listed as
  intentionally identity-keyed, so a subclass whose author *expected* to inherit
  replay is surfaced rather than silently refusing.
"""

from __future__ import annotations

import ast
import inspect
import tempfile
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from pirn.core.hashing import content_hash
from pydantic import BaseModel

from pirn_agents.specializations.structured_output._extraction_tool import _ExtractionTool
from pirn_agents.tools.calculator.calculator_tool import CalculatorTool
from pirn_agents.tools.filesystem.glob_tool import GlobTool
from pirn_agents.tools.filesystem.list_dir_tool import ListDirTool
from pirn_agents.tools.filesystem.read_file_tool import ReadFileTool
from pirn_agents.tools.filesystem.write_file_tool import WriteFileTool
from pirn_agents.tools.function_tool import FunctionTool
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_permissions import ToolPermissions
from pirn_agents.tools.web.html_to_text_tool import HtmlToTextTool
from pirn_agents.tools.web.http_request_tool import HttpRequestTool

#: Classes that define or inherit ``content_identity`` without being production
#: opt-ins, as ``<workspace-relative path>::<class name>``. ``Tool`` declares the
#: default; the test doubles exist to exercise the mechanism itself.
EXEMPT = frozenset(
    {
        "packages/pirn-agents/pirn_agents/tools/tool.py::Tool",
        "packages/pirn-agents/tests/tools/test_tool_content_identity.py::_SameTripleFirstTool",
        "packages/pirn-agents/tests/tools/test_tool_content_identity.py::_SameTripleSecondTool",
    }
)

#: Subclasses of opted-in tools that do not re-declare ``content_identity`` and are
#: therefore identity-keyed on purpose. Each is a reproduction of a false match
#: closed in review of PR #310 (an inherited opt-in, a factory-built class).
INHERITS_WITHOUT_REDECLARING = frozenset(
    {
        "packages/pirn-agents/tests/tools/_cross_process_replay_worker.py::Scaled",
        "packages/pirn-agents/tests/tools/_cross_process_replay_worker.py::TenantReadFile",
        "packages/pirn-agents/tests/tools/test_tool_content_identity.py::Scaled",
        "packages/pirn-agents/tests/tools/test_tool_content_identity.py::_UndeclaredTenantTool",
    }
)

#: The root that declares the default facet; every tool inherits from it, so it
#: must not seed name-based inheritance.
EXEMPT_ROOT = "packages/pirn-agents/pirn_agents/tools/tool.py::Tool"

#: Directory names never scanned: virtualenvs, caches, and git worktrees.
SKIPPED_DIRECTORIES = frozenset(
    {".venv", "venv", "__pycache__", "node_modules", ".git", "build", "dist", ".claude"}
)


class _GateState:
    """Canonical injected state for the ``FunctionTool`` ``state`` variation."""

    def __init__(self, tenant: str) -> None:
        self.tenant = tenant

    def __pirn_canonical__(self) -> dict[str, str]:
        """Declare the tenant as this state's whole identity."""
        return {"tenant": self.tenant}


class _GateArguments(BaseModel):
    a: int


def gate_add(a: int) -> int:
    """Baseline function."""
    return a


def gate_negate(a: int) -> int:
    """Alternate function."""
    return -a


def gate_validator(arguments: Mapping[str, Any]) -> Any:
    """An argument validator with no model behind it."""
    return arguments


class TestOptedInToolsDeclareEveryConstructorArgument(unittest.TestCase):
    def setUp(self) -> None:
        self._root_a = tempfile.TemporaryDirectory()
        self._root_b = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._root_a.cleanup()
        self._root_b.cleanup()

    def cases(
        self,
    ) -> dict[type[Tool], tuple[Callable[[], dict[str, Any]], dict[str, Any], dict[str, str]]]:
        """Return ``{tool type: (baseline kwargs factory, variant per parameter, exclusions)}``.

        An exclusion maps a parameter to the reason varying it need not change the
        hash; it must be justified, and today none is needed.
        """
        root_a, root_b = self._root_a.name, self._root_b.name
        return {
            CalculatorTool: (dict, {}, {}),
            _ExtractionTool: (
                lambda: {
                    "name": "extract",
                    "description": "d",
                    "parameters_schema": {"type": "object"},
                },
                {
                    "name": "other",
                    "description": "other",
                    "parameters_schema": {"type": "array"},
                },
                {},
            ),
            ReadFileTool: (
                lambda: {"root": root_a, "max_bytes": 10},
                {"root": root_b, "max_bytes": 11},
                {},
            ),
            WriteFileTool: (
                lambda: {"root": root_a, "max_bytes": 10},
                {"root": root_b, "max_bytes": 11},
                {},
            ),
            ListDirTool: (
                lambda: {"root": root_a, "max_entries": 10},
                {"root": root_b, "max_entries": 11},
                {},
            ),
            GlobTool: (
                lambda: {"root": root_a, "max_results": 10},
                {"root": root_b, "max_results": 11},
                {},
            ),
            HtmlToTextTool: (lambda: {"max_chars": 10}, {"max_chars": 11}, {}),
            HttpRequestTool: (
                lambda: {
                    "allowed_hosts": ("a.example",),
                    "max_bytes": 10,
                    "timeout": 1.0,
                    "connect_timeout": 1.0,
                    "allow_private": False,
                },
                {
                    "allowed_hosts": ("b.example",),
                    "max_bytes": 11,
                    "timeout": 2.0,
                    "connect_timeout": 2.0,
                    "allow_private": True,
                    "client": object(),
                    "resolver": gate_validator,
                },
                {},
            ),
            FunctionTool: (
                lambda: {
                    "fn": gate_add,
                    "name": "gate_add",
                    "description": "d",
                    "parameters_schema": {"type": "object"},
                    "is_async": False,
                },
                {
                    "fn": gate_negate,
                    "name": "other",
                    "description": "other",
                    "parameters_schema": {"type": "array"},
                    "is_async": True,
                    "return_schema": {"type": "integer"},
                    "permissions": ToolPermissions(mutating=True),
                    "args_validator": gate_validator,
                    "is_streaming": True,
                    "state": _GateState("prod"),
                    "is_stateful": True,
                    "args_model": _GateArguments,
                },
                {},
            ),
        }

    def test_each_case_covers_exactly_the_constructor_signature(self) -> None:
        for tool_type, (_, variants, excluded) in self.cases().items():
            with self.subTest(tool=tool_type.__name__):
                parameters = (
                    set()
                    if tool_type.__init__ is object.__init__
                    else set(inspect.signature(tool_type.__init__).parameters) - {"self"}
                )

                assert set(variants) | set(excluded) == parameters
                assert not set(variants) & set(excluded)

    def test_each_baseline_is_content_identified_and_stable(self) -> None:
        for tool_type, (baseline, _, _) in self.cases().items():
            with self.subTest(tool=tool_type.__name__):
                first, second = tool_type(**baseline()), tool_type(**baseline())

                assert first.content_identity() is not None
                assert content_hash(first) == content_hash(second)

    def test_varying_any_constructor_argument_changes_the_hash(self) -> None:
        for tool_type, (baseline, variants, _) in self.cases().items():
            reference = content_hash(tool_type(**baseline()))
            for parameter, value in variants.items():
                with self.subTest(tool=tool_type.__name__, parameter=parameter):
                    varied = tool_type(**{**baseline(), parameter: value})

                    assert content_hash(varied) != reference

    def test_every_opted_in_class_in_the_workspace_has_a_case(self) -> None:
        found, _ = self._scan(self._workspace_root())
        covered = {
            finding
            for finding in found
            if any(self._is_case_for(finding, tool_type) for tool_type in self.cases())
        }

        assert found == covered | EXEMPT, (
            "a class opts in to content identity without a gate case (or an exemption "
            f"names a class that no longer opts in): {sorted(found ^ (covered | EXEMPT))}"
        )
        assert len(covered) == len(self.cases()), (
            "a gate case names a class the workspace scan no longer finds opting in"
        )

    def test_every_subclass_that_does_not_redeclare_is_intentionally_identity_keyed(
        self,
    ) -> None:
        _, inheriting = self._scan(self._workspace_root())

        assert inheriting == INHERITS_WITHOUT_REDECLARING, (
            "a subclass of an opted-in tool does not re-declare content_identity, so it is "
            "identity-keyed; re-declare it with the subclass's config, or list it here: "
            f"{sorted(inheriting ^ INHERITS_WITHOUT_REDECLARING)}"
        )

    def test_every_loaded_opted_in_tool_has_a_case(self) -> None:
        """Runtime twin of the AST scan: catches opt-ins reached by dynamic bases."""
        uncovered = [
            f"{tool_type.__module__}.{tool_type.__qualname__}"
            for tool_type in self._all_subclasses(Tool)
            if "content_identity" in vars(tool_type)
            and tool_type not in self.cases()
            and not any(self._is_case_for(entry, tool_type) for entry in EXEMPT)
        ]

        assert uncovered == []

    @staticmethod
    def _is_case_for(finding: str, tool_type: type) -> bool:
        path, name = finding.rsplit("::", 1)
        module_path = tool_type.__module__.replace(".", "/") + ".py"
        return name == tool_type.__name__ and path.endswith(module_path)

    @staticmethod
    def _all_subclasses(root: type) -> set[type]:
        found: set[type] = set()
        pending = [root]
        while pending:
            for subclass in pending.pop().__subclasses__():
                if subclass not in found:
                    found.add(subclass)
                    pending.append(subclass)
        return found

    @staticmethod
    def _workspace_root() -> Path:
        for candidate in Path(__file__).resolve().parents:
            if (candidate / "packages").is_dir() and (candidate / "examples").is_dir():
                return candidate
        raise AssertionError(
            "workspace root (a directory holding packages/ and examples/) not found above "
            f"{__file__}; the coverage scan must see the whole workspace"
        )

    @staticmethod
    def _scan(workspace: Path) -> tuple[set[str], set[str]]:
        """Return ``(declaring, inheriting without re-declaring)`` as ``path::name`` sets.

        Inheritance is resolved by base-class *name* to a fixed point, which
        over-reports on a name collision — the safe direction for a gate. Only
        files whose text mentions a relevant name are parsed, which keeps a
        whole-workspace scan fast without narrowing what it can find.
        """
        sources: dict[str, str] = {}
        for top in ("packages", "examples", "scripts"):
            for source in sorted((workspace / top).rglob("*.py")):
                relative = source.relative_to(workspace)
                if not SKIPPED_DIRECTORIES.intersection(relative.parts):
                    sources[relative.as_posix()] = source.read_text(encoding="utf-8")
        parsed: dict[str, list[ast.ClassDef]] = {}
        opted_in: set[str] = set()
        needles = {"content_identity"}
        while True:
            for path, text in sources.items():
                if path not in parsed and any(needle in text for needle in needles):
                    parsed[path] = [
                        node for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ClassDef)
                    ]
            names = {entry.rsplit("::", 1)[1] for entry in opted_in - {EXEMPT_ROOT}}
            found = {
                f"{path}::{node.name}"
                for path, nodes in parsed.items()
                for node in nodes
                if TestOptedInToolsDeclareEveryConstructorArgument._defines_content_identity(node)
                or names.intersection(
                    TestOptedInToolsDeclareEveryConstructorArgument._base_names(node)
                )
            }
            if found == opted_in:
                declaring = {
                    f"{path}::{node.name}"
                    for path, nodes in parsed.items()
                    for node in nodes
                    if TestOptedInToolsDeclareEveryConstructorArgument._defines_content_identity(
                        node
                    )
                }
                return declaring, opted_in - declaring
            opted_in = found
            needles = {"content_identity"} | {
                entry.rsplit("::", 1)[1] for entry in opted_in - {EXEMPT_ROOT}
            }

    @staticmethod
    def _defines_content_identity(node: ast.ClassDef) -> bool:
        return any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == "content_identity"
            for item in node.body
        )

    @staticmethod
    def _base_names(node: ast.ClassDef) -> set[str]:
        return {
            base.id if isinstance(base, ast.Name) else base.attr
            for base in node.bases
            if isinstance(base, (ast.Name, ast.Attribute))
        }
