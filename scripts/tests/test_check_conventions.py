"""Tests for the house-convention gate.

Every rule gets a pair: a fixture that *violates* it, asserted to fire, and a fixture
that is clean, asserted not to. A gate rule with no failing fixture is a rule nobody has
ever seen work — that is how 146 real violations survived a green gate (PIR-873).

Fixtures are written into a throwaway repository laid out like the real one
(``packages/<dist>/<import root>/``) with a miniature pirn-core, so the class hierarchy
index resolves bases exactly as it does in the workspace.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_conventions import CheckConventions
from gatekit.convention_scan import ConventionScan
from gatekit.knot_design_checker import KnotDesignChecker
from gatekit.suppression_rule_catalog import SuppressionRuleCatalog

_ruff = str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "ruff")


def _framework(repo: Path) -> Path:
    """A miniature pirn-core: ``Knot``, ``Gate``, ``Aggregator``, ``Payload``, a Check."""
    core = repo / "packages" / "pirn-core" / "pirn"
    for package in ("", "core", "nodes", "nodes/gate"):
        directory = core / package if package else core
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text("", encoding="utf-8")
    (core / "core" / "knot.py").write_text(
        "class Knot:\n"
        "    async def process(self, **_: object) -> object: ...\n"
        "    def _bootstrap(self, **_: object) -> None: ...\n",
        encoding="utf-8",
    )
    (core / "core" / "payload.py").write_text(
        "class Payload:\n"
        "    @property\n"
        "    def metadata(self) -> dict[str, object]:\n"
        "        return self._metadata\n",
        encoding="utf-8",
    )
    (core / "nodes" / "aggregator.py").write_text(
        "from pirn.core.knot import Knot\n\n\nclass Aggregator(Knot): ...\n", encoding="utf-8"
    )
    (core / "nodes" / "gate" / "gate.py").write_text(
        "from pirn.core.knot import Knot\n\n\nclass Gate(Knot): ...\n", encoding="utf-8"
    )
    (core / "check.py").write_text(
        "from pirn.core.knot import Knot\n\n\nclass Check(Knot): ...\n", encoding="utf-8"
    )
    return core


def _write(repo: Path, relative: str, source: str) -> Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    for parent in path.parents:
        if parent == repo:
            break
        # Only the import root and its subpackages are importable packages: a
        # distribution directory (``pirn-widgets``) must NOT get an ``__init__.py``,
        # or the dotted module name would start with the distribution name.
        if parent.name in {"tests", "packages"} or "-" in parent.name:
            continue
        if not (parent / "__init__.py").exists():
            (parent / "__init__.py").write_text("", encoding="utf-8")
    path.write_text(source, encoding="utf-8")
    return path


def _rules(repo: Path, relative: str, source: str) -> list[str]:
    """The rules the gate reports for one fixture file written into ``repo``."""
    _framework(repo)
    path = _write(repo, relative, source)
    scan = CheckConventions.build_scan(repo, [path], _ruff)
    return sorted(violation.rule for violation in scan.run())


def _source_rules(repo: Path, source: str, name: str = "widget.py") -> list[str]:
    return _rules(repo, f"packages/pirn-widgets/pirn_widgets/{name}", source)


def _test_rules(repo: Path, source: str, name: str = "test_widget.py") -> list[str]:
    return _rules(repo, f"packages/pirn-widgets/tests/{name}", source)


# --------------------------------------------------------------------- structure


def test_multi_class_file_fires_and_one_class_file_is_clean(tmp_path: Path) -> None:
    two = "class Widget:\n    pass\n\n\nclass Gadget:\n    pass\n"
    assert "multi_class_file" in _source_rules(tmp_path / "a", two)
    assert _source_rules(tmp_path / "b", "class Widget:\n    pass\n") == []


def test_module_level_function_fires_unless_dunder_or_knot_factory(tmp_path: Path) -> None:
    assert "module_level_function" in _source_rules(tmp_path / "a", "def build() -> None: ...\n")
    assert _source_rules(tmp_path / "b", "def __getattr__(name: str) -> None: ...\n") == []
    factory = "from pirn.core.knot import Knot\n\n\n@Knot.knot\ndef widget() -> None: ...\n"
    assert "module_level_function" not in _source_rules(tmp_path / "c", factory)


def test_filename_mismatch_compares_alnum_lowercase(tmp_path: Path) -> None:
    assert (
        _source_rules(tmp_path / "a", "class OpenAIClient:\n    pass\n", "open_ai_client.py") == []
    )
    assert "filename_mismatch" in _source_rules(tmp_path / "b", "class Gadget:\n    pass\n")


def test_nested_def_needs_the_override_marker(tmp_path: Path) -> None:
    nested = (
        "class Widget:\n"
        "    def run(self) -> None:\n"
        "        def inner() -> None: ...\n"
        "        inner()\n"
    )
    assert "nested_def_missing_override" in _source_rules(tmp_path / "a", nested)
    marked = (
        "class Widget:\n"
        "    def run(self) -> None:\n"
        "        # design-decision-override: the callback must close over run's frame\n"
        "        def inner() -> None: ...\n"
        "        inner()\n"
    )
    assert "nested_def_missing_override" not in _source_rules(tmp_path / "b", marked)


# --------------------------------------------------------------------- constants


def test_module_level_constant_fires_whatever_its_case(tmp_path: Path) -> None:
    assert "module_level_constant" in _source_rules(tmp_path / "a", "_gr_clean = 20.0\n")
    assert "module_level_constant" in _source_rules(tmp_path / "b", "GR_CLEAN = 20.0\n")
    on_class = (
        "from typing import ClassVar\n\n\nclass Widget:\n    _gr_clean: ClassVar[float] = 20.0\n"
    )
    assert "module_level_constant" not in _source_rules(tmp_path / "c", on_class)


def test_module_level_constant_sees_inside_compound_blocks(tmp_path: Path) -> None:
    """The old rule read ``tree.body`` only, so a compound block hid a constant."""
    guarded = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    _limit = 5\n"
    assert "module_level_constant" in _source_rules(tmp_path / "a", guarded)
    tried = "try:\n    _limit = 5\nexcept ValueError:\n    _limit = 6\n"
    assert "module_level_constant" in _source_rules(tmp_path / "b", tried)


def test_type_aliases_and_dunders_are_not_constants(tmp_path: Path) -> None:
    aliases = (
        "from typing import Any, TypeVar\n\n"
        "__all__ = ['Widget']\n"
        "JsonValue = dict[str, Any]\n"
        "Number = int | float\n"
        "T = TypeVar('T')\n\n\n"
        "class Widget:\n    pass\n"
    )
    assert _source_rules(tmp_path, aliases) == []


# --------------------------------------------------------------------- knot design


def _knot(body: str, base: str = "Knot") -> str:
    imports = "from pirn.core.knot import Knot\nfrom pirn.check import Check\n"
    return f"{imports}\n\nclass Widget({base}):\n{body}"


def test_knot_is_found_through_an_intermediate_and_a_subscripted_base(tmp_path: Path) -> None:
    """The base-*name* list missed 61 real knots: ``Check``, ``Router``, ``Base[T]``."""
    through_check = _knot(
        "    def __init__(self, *, thing: object) -> None:\n        self._thing = thing\n",
        base="Check",
    )
    assert "knot_self_assignment" in _source_rules(tmp_path / "a", through_check)
    subscripted = (
        "from typing import Generic, TypeVar\n\n"
        "from pirn.core.knot import Knot\n\n"
        "S = TypeVar('S')\n\n\n"
        "class Base(Knot, Generic[S]): ...\n"
    )
    _framework(tmp_path / "b")
    _write(tmp_path / "b", "packages/pirn-widgets/pirn_widgets/base.py", subscripted)
    loop = (
        "from pirn_widgets.base import Base\n\n\n"
        "class Widget(Base[int]):\n"
        "    def __init__(self, *, thing: object) -> None:\n"
        "        self._thing = thing\n"
    )
    assert "knot_self_assignment" in _source_rules(tmp_path / "b", loop)


def test_a_class_that_only_reuses_a_root_name_is_not_a_knot(tmp_path: Path) -> None:
    """``class Source:`` in someone else's file is not ``pirn.nodes.source.Source``."""
    impostor = (
        "class Source:\n"
        "    def __init__(self, *, thing: object) -> None:\n"
        "        self._thing = thing\n"
    )
    assert _source_rules(tmp_path, impostor, "source.py") == []


def test_knot_self_assignment_judges_the_value_not_the_attribute(tmp_path: Path) -> None:
    stores_input = _knot(
        "    def __init__(self, *, llm: object) -> None:\n"
        "        self._llm = llm\n"
        "        super().__init__()\n"
    )
    assert "knot_self_assignment" in _source_rules(tmp_path / "a", stores_input)
    latch = _knot(
        "    def __init__(self) -> None:\n        super().__init__()\n        self._frozen = True\n"
    )
    assert "knot_self_assignment" not in _source_rules(tmp_path / "b", latch)
    mutable = _knot(
        "    def __init__(self, *, llm: object) -> None:\n"
        "        super().__init__()\n"
        "        self._mutable_llm = llm\n"
    )
    assert "knot_self_assignment" not in _source_rules(tmp_path / "c", mutable)


def test_knot_init_rejects_work_and_accepts_guards_and_wiring(tmp_path: Path) -> None:
    works = _knot(
        "    def __init__(self, *, path: str) -> None:\n"
        "        rows = open(path).read()\n"
        "        super().__init__(rows=rows)\n"
    )
    assert "knot_init_impure" in _source_rules(tmp_path / "a", works)
    guarded = _knot(
        "    def __init__(self, *, count: int, extra: object | None = None) -> None:\n"
        "        if not isinstance(count, int):\n"
        "            raise TypeError('count must be an int')\n"
        "        parents = {'count': count}\n"
        "        if extra is not None:\n"
        "            parents['extra'] = extra\n"
        "        super().__init__(**parents)\n"
    )
    assert _source_rules(tmp_path / "b", guarded) == []


def test_knot_super_init_argument_sees_work_inside_the_parentheses(tmp_path: Path) -> None:
    """The old rule never looked at the arguments, so the logic moved in there."""
    computed = _knot(
        "    def __init__(self, *, paths: list[str]) -> None:\n"
        "        super().__init__(cache={k: open(k).read() for k in paths})\n"
    )
    assert "knot_super_init_argument" in _source_rules(tmp_path / "a", computed)
    numbered = _knot(
        "    def __init__(self, *, models: list[object]) -> None:\n"
        "        super().__init__(**{f'model_{i}': m for i, m in enumerate(models)})\n"
    )
    assert _source_rules(tmp_path / "b", numbered) == []


def test_knot_property_and_process_kwargs(tmp_path: Path) -> None:
    prop = _knot("    @property\n    def size(self) -> int:\n        return 1\n")
    assert "knot_property" in _source_rules(tmp_path / "a", prop)
    kwargs = _knot("    async def process(self, **kwargs: object) -> None: ...\n")
    assert "knot_process_kwargs_name" in _source_rules(tmp_path / "b", kwargs)
    catch_all = _knot("    async def process(self, **_: object) -> None: ...\n")
    assert "knot_process_kwargs_name" not in _source_rules(tmp_path / "c", catch_all)


def test_gate_base_is_resolved_and_pytest_suites_are_not_gates(tmp_path: Path) -> None:
    wrong = "class WidgetGate:\n    pass\n"
    assert "gate_wrong_base" in _source_rules(tmp_path / "a", wrong, "widget_gate.py")
    right = "from pirn.nodes.gate.gate import Gate\n\n\nclass WidgetGate(Gate):\n    pass\n"
    assert _source_rules(tmp_path / "b", right, "widget_gate.py") == []
    suite = "class TestWidgetGate:\n    def test_it(self) -> None: ...\n"
    assert "gate_wrong_base" not in _source_rules(tmp_path / "c", suite, "test_widget_gate.py")


def test_only_the_named_framework_roots_are_exempt(tmp_path: Path) -> None:
    """The exemption is a qualified class id, not a file name anywhere in core."""
    assert KnotDesignChecker.framework_root_ids == frozenset(
        {
            "pirn.core.knot.Knot",
            "pirn.nodes.aggregator.Aggregator",
            "pirn.core.parameter.Parameter",
        }
    )
    impostor = (
        "from pirn.core.knot import Knot\n\n\n"
        "class Aggregator(Knot):\n"
        "    def __init__(self, *, thing: object) -> None:\n"
        "        self._thing = thing\n"
    )
    rules = _rules(
        tmp_path,
        "packages/pirn-core/pirn/connectors/queue/aggregator.py",
        impostor,
    )
    assert "knot_self_assignment" in rules


def test_the_knot_purity_path_allowlist_is_gone(tmp_path: Path) -> None:
    """``pirn/nodes/`` used to be exempt wholesale, hiding 28 findings."""
    offender = (
        "from pirn.core.knot import Knot\n\n\n"
        "class Widget(Knot):\n"
        "    def __init__(self, *, path: str) -> None:\n"
        "        rows = open(path).read()\n"
        "        super().__init__(rows=rows)\n"
    )
    rules = _rules(tmp_path, "packages/pirn-core/pirn/nodes/widget.py", offender)
    assert "knot_init_impure" in rules


# --------------------------------------------------------------------- aliases


def test_module_alias_of_a_callable_fires_and_a_marker_does_not(tmp_path: Path) -> None:
    renamed = "class Widget:\n    pass\n\n\nOldWidget = Widget\n"
    assert "module_alias_assignment" in _source_rules(tmp_path / "a", renamed)
    marker = "import pytest\n\npytestmark = pytest.mark.slow\n"
    assert "module_alias_assignment" not in _test_rules(tmp_path / "b", marker)


def test_call_rooted_module_alias_fires(tmp_path: Path) -> None:
    """``available_extras = CapabilityProbe().available_extras`` — the shape the old
    "value is a Name or an Attribute" test could not see."""
    probe = (
        "class CapabilityProbe:\n    def available_extras(self) -> list[str]:\n        return []\n"
    )
    _framework(tmp_path)
    _write(tmp_path, "packages/pirn-widgets/pirn_widgets/capability_probe.py", probe)
    lifted = (
        "from pirn_widgets.capability_probe import CapabilityProbe\n\n"
        "available_extras = CapabilityProbe().available_extras\n"
    )
    assert "module_alias_assignment" in _source_rules(tmp_path, lifted, "widget.py")


def test_a_path_value_is_not_a_call_rooted_alias(tmp_path: Path) -> None:
    value = "from pathlib import Path\n\nhere = Path(__file__).resolve().parent\n"
    assert "module_alias_assignment" not in _source_rules(tmp_path, value)


def test_class_scope_alias_of_a_sibling_method_fires(tmp_path: Path) -> None:
    alias = "class Widget:\n    def build(self) -> None: ...\n\n    make = build\n"
    assert "class_alias_assignment" in _source_rules(tmp_path / "a", alias)
    pointer = "class Executor:\n    pass\n"
    _framework(tmp_path / "b")
    _write(tmp_path / "b", "packages/pirn-widgets/pirn_widgets/executor.py", pointer)
    wiring = (
        "from typing import ClassVar\n\n"
        "from pirn_widgets.executor import Executor\n\n\n"
        "class Widget:\n    _executor_class: ClassVar[type[Executor]] = Executor\n"
    )
    assert "class_alias_assignment" not in _source_rules(tmp_path / "b", wiring)


def test_payload_alias_property_sees_a_mapping_get(tmp_path: Path) -> None:
    """``return self.metadata.get("run_id")`` is the same alias as ``[...]``."""
    getter = (
        "from pirn.core.payload import Payload\n\n\n"
        "class Widget(Payload):\n"
        "    @property\n"
        "    def run_id(self) -> object:\n"
        "        return self.metadata.get('run_id')\n"
    )
    assert "payload_alias_property" in _source_rules(tmp_path / "a", getter)
    subscript = (
        "from pirn.core.payload import Payload\n\n\n"
        "class Widget(Payload):\n"
        "    @property\n"
        "    def run_id(self) -> object:\n"
        "        return self.metadata['run_id']\n"
    )
    assert "payload_alias_property" in _source_rules(tmp_path / "b", subscript)
    canonical = (
        "from pirn.core.payload import Payload\n\n\n"
        "class Widget(Payload):\n"
        "    @property\n"
        "    def metadata(self) -> object:\n"
        "        return self._metadata\n"
    )
    assert "payload_alias_property" not in _source_rules(tmp_path / "c", canonical)


# --------------------------------------------------------------------- deprecation


@pytest.mark.parametrize(
    "source",
    [
        "import warnings\n\n\nclass Widget:\n"
        "    def run(self) -> None:\n"
        "        warnings.warn('gone', DeprecationWarning, stacklevel=2)\n",
        "import warnings\n\n\nclass Widget:\n"
        "    def run(self) -> None:\n"
        "        warnings.warn('gone', FutureWarning, stacklevel=2)\n",
        "from warnings import deprecated\n\n\n@deprecated('use Gadget')\nclass Widget:\n    pass\n",
        "from typing import ClassVar\n\n\nclass Widget:\n"
        "    _deprecated_since: ClassVar[str] = '0.9.0'\n",
    ],
    ids=["DeprecationWarning", "FutureWarning", "pep702-deprecated", "since-marker"],
)
def test_every_spelling_of_deprecation_fires(tmp_path: Path, source: str) -> None:
    assert "deprecation_reference" in _source_rules(tmp_path, source)


def test_prose_about_deprecation_is_not_a_deprecation(tmp_path: Path) -> None:
    prose = (
        '"""This module replaced the deprecated Gadget outright."""\n\n\nclass Widget:\n    pass\n'
    )
    assert _source_rules(tmp_path, prose) == []


# --------------------------------------------------------------------- suppressions


def test_a_type_ignore_is_rejected_outright(tmp_path: Path) -> None:
    """pyright reads the bracket as decoration and suppresses the whole line."""
    ignored = (
        "class Widget:\n    value: int = 'x'  # type: ignore[assignment]  # a real reason here\n"
    )
    assert "suppression_without_rule_or_reason" in _source_rules(tmp_path, ignored)


def test_pyright_ignore_needs_a_bracketed_rule_and_a_real_reason(tmp_path: Path) -> None:
    bare = "class Widget:\n    value: int = 1  # pyright: ignore\n"
    assert "suppression_without_rule_or_reason" in _source_rules(tmp_path / "a", bare)
    thin = "class Widget:\n    value: int = 1  # pyright: ignore[reportAssignmentType]  # .\n"
    assert "suppression_without_rule_or_reason" in _source_rules(tmp_path / "b", thin)
    good = (
        "class Widget:\n"
        "    value: int = 1  # pyright: ignore[reportAssignmentType]  # the stub types this as str\n"
    )
    assert _source_rules(tmp_path / "c", good) == []


def test_an_unknown_rule_name_is_reported(tmp_path: Path) -> None:
    unknown = (
        "class Widget:\n"
        "    value: int = 1  # pyright: ignore[notARealRule]  # this suppresses nothing at all\n"
    )
    assert "suppression_unknown_rule" in _source_rules(tmp_path / "a", unknown)
    bad_code = "class Widget:\n    pass  # noqa: XYZ999  # this code does not exist either\n"
    assert "suppression_unknown_rule" in _source_rules(tmp_path / "b", bad_code)


def test_noqa_and_pragma_need_codes_and_reasons(tmp_path: Path) -> None:
    bare = "class Widget:\n    pass  # noqa\n"
    assert "suppression_without_rule_or_reason" in _source_rules(tmp_path / "a", bare)
    unexplained = "class Widget:\n    pass  # noqa: E501\n"
    assert "suppression_without_rule_or_reason" in _source_rules(tmp_path / "b", unexplained)
    pragma = "class Widget:\n    def run(self) -> None:\n        pass  # pragma: no cover\n"
    assert "suppression_without_rule_or_reason" in _source_rules(tmp_path / "c", pragma)
    explained = (
        "class Widget:\n"
        "    def run(self) -> None:\n"
        "        pass  # pragma: no cover  # only runs when the backend is absent\n"
    )
    assert _source_rules(tmp_path / "d", explained) == []


def test_a_file_wide_directive_is_reported(tmp_path: Path) -> None:
    for index, header in enumerate(
        ("# pyright: strict\n", "# ruff: noqa\n", "# mypy: ignore-errors\n")
    ):
        rules = _source_rules(tmp_path / str(index), f"{header}\n\nclass Widget:\n    pass\n")
        assert "file_level_directive" in rules


def test_a_directive_inside_a_string_is_not_a_suppression(tmp_path: Path) -> None:
    quoted = 'class Widget:\n    text = "# type: ignore"\n'
    assert "suppression_without_rule_or_reason" not in _source_rules(tmp_path, quoted)


def test_the_catalog_comes_from_the_installed_tools() -> None:
    catalog = SuppressionRuleCatalog.from_installed_tools(_ruff)
    assert "reportUnusedImport" in catalog.pyright_rules
    assert "E501" in catalog.ruff_codes
    assert "notARealRule" not in catalog.pyright_rules


def test_a_missing_ruff_is_an_error_not_a_pass(tmp_path: Path) -> None:
    with pytest.raises((LookupError, OSError, subprocess.CalledProcessError)):
        SuppressionRuleCatalog.from_installed_tools(str(tmp_path / "no-such-ruff"))


# --------------------------------------------------------------------- scope


def test_test_code_keeps_the_meaning_rules_and_is_spared_the_layout_rules(
    tmp_path: Path,
) -> None:
    messy = (
        "def helper() -> None: ...\n\n\n"
        "class TestOne:\n    pass\n\n\n"
        "class TestTwo:\n"
        "    value: int = 1  # type: ignore[assignment]\n"
    )
    rules = _test_rules(tmp_path / "a", messy)
    assert rules == ["suppression_without_rule_or_reason"]
    assert _source_rules(tmp_path / "b", messy, "test_widget.py") != rules


def test_conftest_counts_as_test_code(tmp_path: Path) -> None:
    messy = "def fixture_one() -> None: ...\n\n\ndef fixture_two() -> None: ...\n"
    assert _rules(tmp_path, "packages/pirn-widgets/pirn_widgets/conftest.py", messy) == []


def test_the_deferred_rule_sets_are_exactly_the_two_families() -> None:
    assert ConventionScan.structural_rules == frozenset(
        {
            "filename_mismatch",
            "module_level_constant",
            "module_level_function",
            "multi_class_file",
            "nested_def_missing_override",
            "reexport_module",
        }
    )
    assert ConventionScan.knot_design_rules == frozenset(
        {
            "gate_wrong_base",
            "knot_init_impure",
            "knot_process_kwargs_name",
            "knot_property",
            "knot_self_assignment",
            "knot_super_init_argument",
        }
    )


# --------------------------------------------------------------------- re-exports


def test_a_reexport_module_fires_even_wrapped_in_a_trivial_if(tmp_path: Path) -> None:
    plain = '"""Old home."""\n\nfrom pirn.core.knot import Knot\n\n__all__ = ["Knot"]\n'
    assert "reexport_module" in _source_rules(tmp_path / "a", plain)
    hatted = (
        '"""Old home."""\n\n'
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    from pirn.core.knot import Knot\n"
    )
    assert "reexport_module" in _source_rules(tmp_path / "b", hatted)
    real = "from pirn.core.knot import Knot\n\n\nclass Widget(Knot):\n    pass\n"
    assert "reexport_module" not in _source_rules(tmp_path / "c", real)


# --------------------------------------------------------------------- CLI


def test_an_unparsable_file_is_a_finding_not_a_silent_skip(tmp_path: Path) -> None:
    assert _source_rules(tmp_path, "class Widget(:\n") == ["unparsable_file"]


def test_main_exits_one_on_a_finding_and_zero_when_clean(tmp_path: Path) -> None:
    _framework(tmp_path)
    path = _write(tmp_path, "packages/pirn-widgets/pirn_widgets/widget.py", "def build(): ...\n")
    argv = [str(path), "--repository-root", str(tmp_path), "--ruff", _ruff]
    assert CheckConventions.main(argv) == 1
    path.write_text("class Widget:\n    pass\n", encoding="utf-8")
    assert CheckConventions.main(argv) == 0


def test_main_rejects_an_unusable_invocation(tmp_path: Path) -> None:
    assert CheckConventions.main([]) == 2
    assert CheckConventions.main([str(tmp_path / "missing")]) == 2
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    assert (
        CheckConventions.main([str(tmp_path), "--repository-root", str(tmp_path), "--ruff", _ruff])
        == 2
    )


def test_the_real_repository_is_scanned_including_tests_examples_and_scripts() -> None:
    """A gate that checked nothing is the failure mode this replaces."""
    repo = Path(__file__).resolve().parents[2]
    scan = CheckConventions.build_scan(
        repo, [repo / "packages", repo / "examples", repo / "scripts"], _ruff
    )
    relative = {str(target.relative_posix) for target in scan.targets()}
    assert scan.checked_file_count > 2000
    assert any(path.startswith("packages/pirn-core/tests/") for path in relative)
    assert any(path.startswith("examples/") for path in relative)
    assert any(path.startswith("scripts/") for path in relative)
    assert "scripts/check_conventions.py" in relative
