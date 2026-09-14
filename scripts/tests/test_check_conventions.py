"""Tests for the house-conventions AST gate (PIR-856)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_conventions  # noqa: E402
from check_conventions import (  # noqa: E402
    check_file,
    collect_counts,
    main,
    resolve_import_roots,
)


def _import_root(tmp_path: Path, dist_name: str, import_name: str) -> Path:
    """Create ``tmp_path/<dist_name>/<import_name>/`` as an import root."""
    root = tmp_path / dist_name / import_name
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("")
    return root


def _rules(violations: list) -> list[str]:
    return [v.rule for v in violations]


# --- rule 1: multi_class_file -----------------------------------------------


def test_flags_more_than_one_top_level_class(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "two.py"
    f.write_text("class A: ...\n\n\nclass B: ...\n")
    violations = check_file(f, "acme", "two.py")
    assert "multi_class_file" in _rules(violations)


def test_single_class_file_is_clean(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "one.py"
    f.write_text("class One: ...\n")
    assert "multi_class_file" not in _rules(check_file(f, "acme", "one.py"))


# --- rule 2: module_level_function ------------------------------------------


def test_flags_module_level_function(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "funcs.py"
    f.write_text("def helper() -> None:\n    pass\n")
    violations = check_file(f, "acme", "funcs.py")
    assert "module_level_function" in _rules(violations)


def test_dunder_function_is_exempt(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "dunder.py"
    f.write_text("def __getattr__(name: str):\n    raise AttributeError(name)\n")
    assert "module_level_function" not in _rules(check_file(f, "acme", "dunder.py"))


def test_knot_decorated_function_is_exempt(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "factory.py"
    f.write_text(
        "from pirn.core.knot_factory import KnotFactory\n\n\n@KnotFactory.knot\ndef make_thing():\n    pass\n"
    )
    assert "module_level_function" not in _rules(check_file(f, "acme", "factory.py"))


def test_bare_alias_assignment_is_not_a_module_level_function(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "renderer.py"
    f.write_text(
        "class Renderer:\n"
        "    @staticmethod\n"
        "    def render(x: int) -> int:\n"
        "        return x\n\n\n"
        "render = Renderer.render\n"
    )
    assert "module_level_function" not in _rules(check_file(f, "acme", "acme/renderer.py"))


# --- rule 3: nested_def_missing_override ------------------------------------


def test_flags_nested_function_without_override_comment(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "closures.py"
    f.write_text("def outer():\n    def inner():\n        pass\n    return inner\n")
    violations = check_file(f, "acme", "closures.py")
    assert "nested_def_missing_override" in _rules(violations)


def test_nested_function_with_override_comment_is_allowed(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "closures.py"
    f.write_text(
        "def outer():\n"
        "    #design-decision-override: closure captures config\n"
        "    def inner():\n"
        "        pass\n"
        "    return inner\n"
    )
    assert "nested_def_missing_override" not in _rules(
        check_file(f, "acme", "closures.py")
    )


def test_method_inside_class_is_not_nested(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "widget.py"
    f.write_text("class Widget:\n    def method(self) -> None:\n        pass\n")
    assert "nested_def_missing_override" not in _rules(
        check_file(f, "acme", "widget.py")
    )


# --- rule 4: gate_wrong_base -------------------------------------------------


def test_flags_gate_suffix_with_wrong_base(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "eval_gate.py"
    f.write_text("class EvalGate:\n    pass\n")
    assert "gate_wrong_base" in _rules(check_file(f, "acme", "eval_gate.py"))


def test_allows_gate_suffix_extending_gate_primitive(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "row_count_gate.py"
    f.write_text(
        "from pirn.nodes.gate.gate import Gate\n\n\nclass RowCountGate(Gate):\n    pass\n"
    )
    assert "gate_wrong_base" not in _rules(check_file(f, "acme", "row_count_gate.py"))


def test_gate_primitive_itself_is_not_flagged(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "gate.py"
    f.write_text("from pirn.core.knot import Knot\n\n\nclass Gate(Knot):\n    pass\n")
    assert "gate_wrong_base" not in _rules(check_file(f, "acme", "gate.py"))


# --- rules 5-7: Knot purity (init, self-assignment, property) --------------


def test_flags_impure_knot_init(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\n"
        "class ThingKnot(Knot):\n"
        "    def __init__(self, *, x, _config, **kwargs) -> None:\n"
        "        if not x:\n"
        "            raise ValueError('x required')\n"
        "        super().__init__(x=x, _config=_config, **kwargs)\n"
    )
    assert "knot_init_impure" in _rules(check_file(f, "acme", "thing_knot.py"))


def test_allows_pure_knot_init(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\n"
        "class ThingKnot(Knot):\n"
        "    def __init__(self, *, x, _config, **kwargs) -> None:\n"
        '        """Wire x through."""\n'
        "        super().__init__(x=x, _config=_config, **kwargs)\n"
    )
    assert "knot_init_impure" not in _rules(check_file(f, "acme", "thing_knot.py"))


def test_allows_knot_with_no_init(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\nclass ThingKnot(Knot):\n    pass\n"
    )
    assert "knot_init_impure" not in _rules(check_file(f, "acme", "thing_knot.py"))


def test_flags_self_assignment_in_knot_init(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\n"
        "class ThingKnot(Knot):\n"
        "    def __init__(self, *, x, _config, **kwargs) -> None:\n"
        "        self._x = x\n"
        "        super().__init__(x=x, _config=_config, **kwargs)\n"
    )
    assert "knot_self_assignment" in _rules(check_file(f, "acme", "thing_knot.py"))


def test_mutable_prefixed_self_assignment_is_allowed(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\n"
        "class ThingKnot(Knot):\n"
        "    def __init__(self, *, x, _config, **kwargs) -> None:\n"
        "        self._mutable_cache = {}\n"
        "        super().__init__(x=x, _config=_config, **kwargs)\n"
    )
    assert "knot_self_assignment" not in _rules(check_file(f, "acme", "thing_knot.py"))


def test_flags_property_on_knot_subclass(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\n"
        "class ThingKnot(Knot):\n"
        "    @property\n"
        "    def column(self) -> str:\n"
        "        return self._column\n"
    )
    assert "knot_property" in _rules(check_file(f, "acme", "thing_knot.py"))


def test_flags_cached_property_on_knot_subclass(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from functools import cached_property\n\n"
        "from pirn.core.knot import Knot\n\n\n"
        "class ThingKnot(Knot):\n"
        "    @cached_property\n"
        "    def column(self) -> str:\n"
        "        return 'x'\n"
    )
    assert "knot_property" in _rules(check_file(f, "acme", "thing_knot.py"))


def test_property_on_plain_class_is_not_flagged(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "widget.py"
    f.write_text(
        "class Widget:\n    @property\n    def name(self) -> str:\n        return self._name\n"
    )
    assert "knot_property" not in _rules(check_file(f, "acme", "widget.py"))


# --- rule 8: knot_process_kwargs_name ---------------------------------------


def test_flags_wrongly_named_process_kwargs(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\n"
        "class ThingKnot(Knot):\n"
        "    async def process(self, x: int, **kwargs) -> int:\n"
        "        return x\n"
    )
    assert "knot_process_kwargs_name" in _rules(check_file(f, "acme", "thing_knot.py"))


def test_allows_underscore_named_process_kwargs(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\n"
        "class ThingKnot(Knot):\n"
        "    async def process(self, x: int, **_) -> int:\n"
        "        return x\n"
    )
    assert "knot_process_kwargs_name" not in _rules(
        check_file(f, "acme", "thing_knot.py")
    )


def test_process_with_no_kwargs_param_is_not_flagged_by_this_rule(
    tmp_path: Path,
) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "thing_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\nclass ThingKnot(Knot):\n    async def process(self, x: int) -> int:\n        return x\n"
    )
    assert "knot_process_kwargs_name" not in _rules(
        check_file(f, "acme", "thing_knot.py")
    )


# --- rule 9: filename_mismatch ----------------------------------------------


def test_flags_filename_not_matching_class(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "foo.py"
    f.write_text("class Bar:\n    pass\n")
    assert "filename_mismatch" in _rules(check_file(f, "acme", "foo.py"))


def test_alnum_lowercase_comparison_allows_acronym_class(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "openai_client.py"
    f.write_text("class OpenAIClient:\n    pass\n")
    assert "filename_mismatch" not in _rules(check_file(f, "acme", "openai_client.py"))


def test_private_only_class_file_is_not_checked(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "__init__.py"
    f.write_text("class _Helper:\n    pass\n")
    assert "filename_mismatch" not in _rules(check_file(f, "acme", "__init__.py"))


# --- knot-like class detection (base name or suffix) ------------------------


def test_pipeline_suffix_counts_as_knot_like_even_without_knot_base(
    tmp_path: Path,
) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "score_pipeline.py"
    f.write_text(
        "class ScorePipeline:\n    def __init__(self, *, x) -> None:\n        self.x = x\n"
    )
    assert "knot_self_assignment" in _rules(check_file(f, "acme", "score_pipeline.py"))


# --- core-lane allowlist (rules 5-7 only) -----------------------------------


def test_core_nodes_allowlist_exempts_rules_5_to_7() -> None:
    assert check_conventions._is_exempt_from_knot_purity(
        "pirn-core", "pirn/nodes/gate/gate.py"
    )
    assert check_conventions._is_exempt_from_knot_purity(
        "pirn-core", "pirn/core/parameter.py"
    )
    assert not check_conventions._is_exempt_from_knot_purity(
        "pirn-core", "pirn/connectors/foo.py"
    )
    assert not check_conventions._is_exempt_from_knot_purity(
        "pirn-agents", "pirn/nodes/gate/gate.py"
    )


def test_allowlisted_file_still_checked_for_process_kwargs(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "pirn-core", "pirn")
    nodes = root / "nodes"
    nodes.mkdir()
    f = nodes / "some_knot.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\n"
        "class SomeKnot(Knot):\n"
        "    def __init__(self, *, x) -> None:\n"
        "        self.x = x\n"
        "    async def process(self, x, **kwargs):\n"
        "        return x\n"
    )
    violations = _rules(check_file(f, "pirn-core", "pirn/nodes/some_knot.py"))
    assert "knot_self_assignment" not in violations
    assert "knot_init_impure" not in violations
    assert "knot_process_kwargs_name" in violations


# --- framework root definitions (rules 5-8) ---------------------------------

_ROOT_KNOT_SOURCE = (
    "from typing import Any\n\n\n"
    "class Knot:\n"
    "    def __init__(self, **kwargs: Any) -> None:\n"
    "        config = kwargs.pop('_config')\n"
    "        self._mutable_config = config\n"
    "        self._frozen = True\n\n"
    "    @property\n"
    "    def knot_id(self) -> str:\n"
    "        return self._mutable_config.id\n\n"
    "    async def process(self, *args: Any, **kwargs: Any) -> Any:\n"
    "        raise NotImplementedError\n"
)

_KNOT_RULES = {
    "knot_init_impure",
    "knot_self_assignment",
    "knot_property",
    "knot_process_kwargs_name",
}


def test_core_knot_root_definition_is_exempt_from_rules_5_to_8(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "pirn-core", "pirn")
    (root / "core").mkdir()
    f = root / "core" / "knot.py"
    f.write_text(_ROOT_KNOT_SOURCE)
    violations = set(_rules(check_file(f, "pirn-core", "pirn/core/knot.py")))
    assert not violations & _KNOT_RULES


def test_core_aggregator_root_definition_keeps_variadic_process(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "pirn-core", "pirn")
    (root / "engine").mkdir()
    f = root / "engine" / "aggregator.py"
    f.write_text(
        "from pirn.core.knot import Knot\n\n\n"
        "class Aggregator(Knot):\n"
        "    async def process(self, **inputs):\n"
        "        return inputs\n"
    )
    assert "knot_process_kwargs_name" not in _rules(
        check_file(f, "pirn-core", "pirn/engine/aggregator.py")
    )


def test_same_named_subclass_of_a_core_root_is_still_checked(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "pirn-core", "pirn")
    (root / "nodes").mkdir()
    f = root / "nodes" / "sub_tapestry.py"
    f.write_text(
        "from pirn.nodes import sub_tapestry\n\n\n"
        "class SubTapestry(sub_tapestry.SubTapestry):\n"
        "    async def process(self, **inputs):\n"
        "        return inputs\n"
    )
    assert "knot_process_kwargs_name" in _rules(
        check_file(f, "pirn-core", "pirn/nodes/sub_tapestry.py")
    )


def test_knot_subclass_in_core_is_still_checked(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "pirn-core", "pirn")
    (root / "core").mkdir()
    f = root / "core" / "fancy_knot.py"
    f.write_text(
        "from typing import Any\n\n"
        "from pirn.core.knot import Knot\n\n\n"
        "class FancyKnot(Knot):\n"
        "    def __init__(self, *, x: Any, **kwargs: Any) -> None:\n"
        "        self._x = x\n"
        "        super().__init__(x=x, **kwargs)\n\n"
        "    @property\n"
        "    def x(self) -> Any:\n"
        "        return self._x\n\n"
        "    async def process(self, x: Any, **kwargs: Any) -> Any:\n"
        "        return x\n"
    )
    violations = set(_rules(check_file(f, "pirn-core", "pirn/core/fancy_knot.py")))
    assert violations >= _KNOT_RULES


def test_root_name_in_another_core_file_is_still_checked(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "pirn-core", "pirn")
    (root / "core").mkdir()
    f = root / "core" / "not_the_root.py"
    f.write_text(_ROOT_KNOT_SOURCE)
    violations = set(_rules(check_file(f, "pirn-core", "pirn/core/not_the_root.py")))
    assert violations >= _KNOT_RULES


def test_root_definition_outside_pirn_core_is_still_checked(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "knot.py"
    f.write_text(_ROOT_KNOT_SOURCE)
    violations = set(_rules(check_file(f, "acme", "acme/knot.py")))
    assert violations >= _KNOT_RULES


# --- file discovery (skips tests/, conftest.py) -----------------------------


def test_collect_counts_skips_tests_dir_and_conftest(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    (root / "real.py").write_text("def leaked() -> None:\n    pass\n")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_real.py").write_text("def helper() -> None:\n    pass\n")
    (root / "conftest.py").write_text("def fixture_helper() -> None:\n    pass\n")

    counts, _violations = collect_counts([root])
    assert counts["acme"]["module_level_function"] == 1


# --- failure semantics: no baseline, any finding fails ------------------------


def _run(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["check_conventions.py", *args])
    return main()


def test_any_finding_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    (root / "leak.py").write_text("def helper() -> None:\n    pass\n")

    exit_code = _run(monkeypatch, str(root))

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "[module_level_function]" in out
    assert "acme: module_level_function 1" in out


def test_clean_tree_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    (root / "clean.py").write_text('"""Clean."""\n\n\nclass Clean:\n    pass\n')

    assert _run(monkeypatch, str(root)) == 0


def test_baseline_options_no_longer_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    for option in (["--baseline", str(tmp_path / "b.json")], ["--write-baseline"]):
        with pytest.raises(SystemExit) as excinfo:
            _run(monkeypatch, str(root), *option)
        assert excinfo.value.code == 2


def test_real_packages_have_no_findings() -> None:
    """The workspace itself is clean under every rule."""
    repo = Path(__file__).resolve().parents[2]
    roots = [r for r in sorted(repo.glob("packages/*/pirn*")) if (r / "__init__.py").exists()]
    _counts, violations = collect_counts(roots)
    assert [str(v) for v in violations] == []


# --- CLI contract -------------------------------------------------------


def test_no_arguments_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(monkeypatch) == 2


def test_missing_path_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(monkeypatch, str(tmp_path / "nope")) == 2


def test_non_directory_path_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = tmp_path / "file.py"
    f.write_text("")
    assert _run(monkeypatch, str(f)) == 2


def test_resolve_import_roots_accepts_directories(tmp_path: Path) -> None:
    root = _import_root(tmp_path, "acme", "acme")
    roots, errors = resolve_import_roots([str(root)])
    assert errors == []
    assert roots == [root]


def test_fan_in_wiring_in_init_is_pure(tmp_path: Path) -> None:
    """Building an Aggregator over a variadic input before super() is wiring, not logic."""
    src = (
        "from pirn.core.knot import Knot\n"
        "from pirn.nodes.aggregator import Aggregator\n"
        "class EnsembleBuilder(Knot):\n"
        "    def __init__(self, *, models, _config, **kwargs):\n"
        "        numbered = {f'model_{i}': m for i, m in enumerate(models)}\n"
        "        node = Aggregator(combine=max, _config=_config, **numbered)\n"
        "        super().__init__(models=node, _config=_config, **kwargs)\n"
        "    async def process(self, models, **_):\n"
        "        return models\n"
    )
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "ensemble_builder.py"
    f.write_text(src)
    assert "knot_init_impure" not in _rules(
        check_file(f, "acme", "ensemble_builder.py")
    )


def test_non_fan_in_logic_in_init_is_impure(tmp_path: Path) -> None:
    src = (
        "from pirn.core.knot import Knot\n"
        "class Bad(Knot):\n"
        "    def __init__(self, *, x, _config, **kwargs):\n"
        "        if x is None:\n"
        "            raise ValueError('x')\n"
        "        super().__init__(x=x, _config=_config, **kwargs)\n"
        "    async def process(self, x, **_):\n"
        "        return x\n"
    )
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "bad.py"
    f.write_text(src)
    assert "knot_init_impure" in _rules(check_file(f, "acme", "bad.py"))


def test_override_marker_survives_ruff_format_spacing(tmp_path: Path) -> None:
    """``ruff format`` inserts a space after ``#``; both spellings must count."""
    root = _import_root(tmp_path, "acme", "acme")
    f = root / "closure.py"
    f.write_text(
        "def outer(x):\n"
        "    # design-decision-override: closure captures x\n"
        "    def inner():\n"
        "        return x\n"
        "    return inner\n"
    )
    assert "nested_def_missing_override" not in _rules(
        check_file(f, "acme", "closure.py")
    )
