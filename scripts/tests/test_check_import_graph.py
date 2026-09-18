"""Tests for the import-graph gate (PIR-873).

The gate used to tolerate a missing package directory, an unparseable source
file and an empty package set — each of which made it check nothing and exit 0 —
and it silently produced phantom edges when run from anywhere but the repo root.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_import_graph import CheckImportGraph

_repo_root = Path(__file__).resolve().parents[2]


def _workspace(tmp_path: Path, *, domains: tuple[str, ...] | None = None) -> Path:
    """A minimal ``packages/`` tree with one source file per domain package."""
    root = tmp_path / "packages"
    for domain in domains if domains is not None else CheckImportGraph._domain_names:
        src = root / f"pirn-{domain}" / f"pirn_{domain}"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
    return root


def _pyproject(root: Path, name: str, dependencies: list[str]) -> None:
    package = root / name
    package.mkdir(parents=True, exist_ok=True)
    deps = ", ".join(f'"{d}"' for d in dependencies)
    (package / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.0.0"\ndependencies = [{deps}]\n'
    )


# --- core-is-sink (C2) ------------------------------------------------------


def test_core_is_sink_accepts_a_clean_tree(tmp_path: Path) -> None:
    src = tmp_path / "pirn"
    src.mkdir()
    (src / "engine.py").write_text("import json\n")
    assert CheckImportGraph.check_core_is_sink(src) == []


def test_core_is_sink_flags_a_domain_import(tmp_path: Path) -> None:
    src = tmp_path / "pirn"
    src.mkdir()
    (src / "engine.py").write_text("from pirn_ml.model import Model\n")
    violations = CheckImportGraph.check_core_is_sink(src)
    assert len(violations) == 1
    assert "pirn_ml.model" in violations[0]


def test_missing_core_source_tree_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        CheckImportGraph.check_core_is_sink(tmp_path / "nope")


def test_core_source_tree_with_no_python_files_is_an_error(tmp_path: Path) -> None:
    empty = tmp_path / "pirn"
    empty.mkdir()
    with pytest.raises(ValueError, match=r"no \.py files"):
        CheckImportGraph.check_core_is_sink(empty)


def test_unparseable_source_file_is_an_error(tmp_path: Path) -> None:
    src = tmp_path / "pirn"
    src.mkdir()
    (src / "broken.py").write_text("def oops(:\n")
    with pytest.raises(ValueError, match="could not parse"):
        CheckImportGraph.check_core_is_sink(src)


# --- domain DAG (C1/C3 over real imports) -----------------------------------


def test_domain_dag_accepts_the_single_retained_edge(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    (root / "pirn-ml" / "pirn_ml" / "frame.py").write_text("import pirn_data\n")
    assert CheckImportGraph.check_domain_dag(root) == []


def test_domain_dag_flags_a_new_cross_domain_edge(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    (root / "pirn-ml" / "pirn_ml" / "frame.py").write_text("import pirn_data\n")
    (root / "pirn-agents" / "pirn_agents" / "tool.py").write_text("import pirn_ml\n")
    violations = CheckImportGraph.check_domain_dag(root)
    assert any("'agents' -> 'ml'" in v for v in violations)


def test_missing_domain_package_directory_is_an_error(tmp_path: Path) -> None:
    # The old gate `continue`d past a missing domain, so it contributed no edges
    # and the graph passed without the domain ever being looked at.
    root = _workspace(tmp_path, domains=("signal", "data", "ml", "agents", "health"))
    with pytest.raises(ValueError, match="pirn_oilgas"):
        CheckImportGraph.check_domain_dag(root)


def test_missing_packages_root_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        CheckImportGraph.check_domain_dag(tmp_path / "nope")


def test_unparseable_domain_source_is_an_error(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    (root / "pirn-ml" / "pirn_ml" / "broken.py").write_text("class Oops(\n")
    with pytest.raises(ValueError, match="could not parse"):
        CheckImportGraph.check_domain_dag(root)


# --- package DAG (C1/C3 over declared deps) ---------------------------------


def test_package_dag_accepts_the_declared_ml_to_data_edge(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    _pyproject(root, "pirn-core", [])
    _pyproject(root, "pirn-data", ["pirn-core>=0.9.0,<0.10.0"])
    _pyproject(root, "pirn-ml", ["pirn-core>=0.9.0,<0.10.0", "pirn-data>=0.9.0,<0.10.0"])
    assert CheckImportGraph.check_package_dag(root) == []


def test_empty_packages_root_is_an_error(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    root.mkdir()
    with pytest.raises(ValueError, match="no packages"):
        CheckImportGraph.check_package_dag(root)


def test_pyproject_without_a_project_name_is_an_error(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    (root / "broken").mkdir(parents=True)
    (root / "broken" / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n')
    with pytest.raises(ValueError, match="no \\[project\\] name"):
        CheckImportGraph.check_package_dag(root)


# --- CLI contract -----------------------------------------------------------


def test_running_outside_the_repository_root_exits_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # From inside a package the walk finds different files and reports phantom
    # edges; the old gate believed them.
    monkeypatch.chdir(tmp_path)
    assert CheckImportGraph.main([]) == 2
    assert "must run from the repository root" in capsys.readouterr().err


def test_missing_src_argument_exits_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(_repo_root)
    assert CheckImportGraph.main(["--core-is-sink", "--src", "packages/nope"]) == 2
    assert "could not run" in capsys.readouterr().err


def test_real_repository_is_a_sink_from_the_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_repo_root)
    assert CheckImportGraph.main(["--core-is-sink"]) == 0


def test_real_repository_dags_hold_from_the_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_repo_root)
    assert CheckImportGraph.main(["--domain-dag", "--package-dag"]) == 0


# --- cycle detection --------------------------------------------------------


def test_find_cycle_detects_a_loop() -> None:
    edges = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
    assert CheckImportGraph._find_cycle(edges) is not None


def test_find_cycle_returns_none_for_a_dag() -> None:
    edges = {"a": {"b"}, "b": {"c"}, "c": set()}
    assert CheckImportGraph._find_cycle(edges) is None


def test_distribution_name_strips_a_version_specifier() -> None:
    assert CheckImportGraph._distribution_name("pirn-core>=0.4.0,<0.5.0") == "pirn-core"


def test_distribution_name_strips_extras_and_a_marker() -> None:
    spec = 'pirn-data[s3] >= 1.0 ; python_version >= "3.12"'
    assert CheckImportGraph._distribution_name(spec) == "pirn-data"


def test_distribution_name_leaves_a_bare_name_alone() -> None:
    assert CheckImportGraph._distribution_name("pirn-ml") == "pirn-ml"
