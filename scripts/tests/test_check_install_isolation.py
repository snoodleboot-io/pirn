"""Tests for the install-isolation gate's submodule walk and derived denylist (PIR-872/873)."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_install_isolation
from check_install_isolation import CheckInstallIsolation
from gatekit.extras_backend_denylist import ExtrasBackendDenylist

_packages_root = Path(__file__).resolve().parents[2] / "packages"


def _package(tmp_path: Path, name: str, modules: dict[str, str]) -> None:
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text("")
    for module, source in modules.items():
        (root / f"{module}.py").write_text(source)


@pytest.fixture
def isolated_modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    monkeypatch.syspath_prepend(str(tmp_path))
    before = set(sys.modules)
    yield tmp_path
    for name in set(sys.modules) - before:
        sys.modules.pop(name, None)


def test_denylist_drops_backends_the_hard_dependency_closure_provides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        CheckInstallIsolation,
        "_hard_dependency_closure",
        lambda _package: {"acme", "numpy"},
    )
    monkeypatch.setattr(
        CheckInstallIsolation,
        "backend_denylist",
        lambda: frozenset({"numpy", "pandas"}),
    )
    monkeypatch.setattr(
        check_install_isolation.importlib.metadata,
        "packages_distributions",
        lambda: {"numpy": ["numpy"], "pandas": ["pandas"]},
    )

    denylist = CheckInstallIsolation._backend_denylist_for("acme")

    assert "numpy" not in denylist
    assert "pandas" in denylist


def test_walk_passes_a_package_that_imports_no_backend(isolated_modules: Path) -> None:
    _package(isolated_modules, "iso_clean_pkg", {"plain": "import json\n"})

    assert (
        CheckInstallIsolation._check_no_backend_after_submodule_walk(
            "iso_clean_pkg", frozenset({"iso_backend_a"})
        )
        == []
    )


def test_walk_reports_a_backend_imported_at_module_scope(
    isolated_modules: Path,
) -> None:
    (isolated_modules / "iso_backend_b.py").write_text("")
    _package(isolated_modules, "iso_leaky_pkg", {"eager": "import iso_backend_b\n"})

    violations = CheckInstallIsolation._check_no_backend_after_submodule_walk(
        "iso_leaky_pkg", frozenset({"iso_backend_b"})
    )

    assert len(violations) == 1
    assert "iso_backend_b" in violations[0]


def test_walk_allows_a_backend_imported_inside_a_method(isolated_modules: Path) -> None:
    (isolated_modules / "iso_backend_c.py").write_text("")
    _package(
        isolated_modules,
        "iso_lazy_pkg",
        {
            "lazy": "class Lazy:\n    @staticmethod\n    def run() -> None:\n        import iso_backend_c\n"
        },
    )

    assert (
        CheckInstallIsolation._check_no_backend_after_submodule_walk(
            "iso_lazy_pkg", frozenset({"iso_backend_c"})
        )
        == []
    )


def test_walk_reports_a_submodule_that_cannot_import(isolated_modules: Path) -> None:
    _package(
        isolated_modules,
        "iso_broken_pkg",
        {"needs_extra": "import iso_missing_backend_zzz\n"},
    )

    violations = CheckInstallIsolation._check_no_backend_after_submodule_walk(
        "iso_broken_pkg", frozenset()
    )

    assert len(violations) == 1
    assert "iso_broken_pkg.needs_extra" in violations[0]


def test_every_package_runs_the_submodule_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    walked: list[str] = []
    monkeypatch.setattr(CheckInstallIsolation, "_check_closure", lambda _package: [])
    monkeypatch.setattr(CheckInstallIsolation, "_check_versions", lambda _package, _version: [])
    monkeypatch.setattr(CheckInstallIsolation, "_check_imports", lambda _package: [])
    monkeypatch.setattr(CheckInstallIsolation, "_backend_denylist_for", lambda _p: frozenset())
    monkeypatch.setattr(
        CheckInstallIsolation,
        "_check_no_backend_after_submodule_walk",
        lambda import_name, _denylist: walked.append(import_name) or [],
    )
    for package in sorted(CheckInstallIsolation._expected_pirn_closure):
        assert (
            CheckInstallIsolation.main(
                ["--package", package, "--expect-version", "0.9.0"],
            )
            == 0
        )

    assert sorted(walked) == sorted(CheckInstallIsolation._import_names.values())


def test_versions_pass_when_the_closure_is_the_build_under_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check_install_isolation.importlib.metadata, "version", lambda _d: "0.9.0")

    assert CheckInstallIsolation._check_versions("pirn-ml", "0.9.0") == []


def test_versions_fail_when_an_index_release_was_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published = {"pirn-core": "0.10.0", "pirn-oilgas": "0.10.0"}
    monkeypatch.setattr(
        check_install_isolation.importlib.metadata, "version", lambda d: published[d]
    )

    violations = CheckInstallIsolation._check_versions("pirn-oilgas", "0.9.0")

    assert len(violations) == 2
    assert "pirn-oilgas==0.10.0" in " ".join(violations)


def test_a_version_mismatch_stops_the_gate_before_the_walk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    walked: list[str] = []
    monkeypatch.setattr(CheckInstallIsolation, "_check_closure", lambda _package: [])
    monkeypatch.setattr(
        CheckInstallIsolation,
        "_check_versions",
        lambda _package, _version: ["wrong release"],
    )
    monkeypatch.setattr(
        CheckInstallIsolation,
        "_check_no_backend_after_submodule_walk",
        lambda import_name, _denylist: walked.append(import_name) or [],
    )

    assert (
        CheckInstallIsolation.main(
            ["--package", "pirn-oilgas", "--expect-version", "0.9.0"],
        )
        == 1
    )
    assert walked == []


# --- PIR-873: the denylist is derived, not hand-written ---------------------
# The hand-written `_BACKEND_DENYLIST` listed 67 modules while the seven
# packages' `[project.optional-dependencies]` declare 159 extra-only
# distributions, so ~95 backends could be imported at module scope and pass.


def test_derived_denylist_covers_every_extra_only_distribution() -> None:
    installed = ExtrasBackendDenylist._installed_top_levels()
    denylist = CheckInstallIsolation.backend_denylist()
    for distribution in ExtrasBackendDenylist.extra_only_distributions(_packages_root):
        names = ExtrasBackendDenylist.import_names(distribution, installed)
        assert names, f"{distribution} resolved to no import name"
        assert set(names) <= set(denylist), f"{distribution} is missing from the denylist"


@pytest.mark.parametrize(
    "module",
    [
        # pirn-ml [ml]
        "sklearn",
        # pirn-health [health] / [genomics] / [mri]
        "pyedflib",
        "openslide",
        "defusedxml",
        "fhir",
        # pirn-oilgas [oilgas]
        "dlisio",
        # pirn-signal [signal]
        "pywt",
        # pirn-core storage / saas / stream extras
        "azure",
        "google",
        "oracledb",
        "netCDF4",
        "PIL",
        "shapefile",
        "slack_sdk",
        "valkey",
        # pirn-data extras
        "sqlglot",
        "bytewax",
        "pathway",
    ],
)
def test_denylist_contains_backends_the_hand_written_list_missed(module: str) -> None:
    assert module in CheckInstallIsolation.backend_denylist()


def test_derived_denylist_excludes_hard_dependencies_and_pirn_itself() -> None:
    denylist = CheckInstallIsolation.backend_denylist()
    # numpy / pyyaml / pydantic are pirn-core hard dependencies, present in every
    # base install; pirn-* are the packages under test, not optional backends.
    for allowed in ("numpy", "yaml", "pydantic", "cloudpickle", "pirn", "pirn_ml"):
        assert allowed not in denylist


def test_unmappable_distribution_is_an_error_not_a_silent_drop() -> None:
    with pytest.raises(ValueError, match="cannot map distribution"):
        ExtrasBackendDenylist.import_names("4suite-xml", {})


def test_unmappable_distribution_exits_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(CheckInstallIsolation, "_check_closure", lambda _package: [])
    monkeypatch.setattr(CheckInstallIsolation, "_check_versions", lambda _package, _version: [])
    monkeypatch.setattr(CheckInstallIsolation, "_check_imports", lambda _package: [])
    monkeypatch.setattr(
        ExtrasBackendDenylist,
        "extra_only_distributions",
        lambda _root: {"4suite-xml"},
    )

    exit_code = CheckInstallIsolation.main(["--package", "pirn-core", "--expect-version", "0.9.0"])

    assert exit_code == 2
    assert "cannot map distribution" in capsys.readouterr().err


def test_missing_packages_root_is_an_error() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        ExtrasBackendDenylist.derive(Path("/nonexistent-packages-root"))


def test_workspace_with_no_pyprojects_is_an_error(tmp_path: Path) -> None:
    empty = tmp_path / "packages"
    empty.mkdir()
    with pytest.raises(ValueError, match=r"no packages/\*/pyproject\.toml"):
        ExtrasBackendDenylist.derive(empty)


def test_installed_metadata_wins_over_the_override_table() -> None:
    names = ExtrasBackendDenylist.import_names("scikit-learn", {"scikit-learn": {"sklearn_x"}})
    assert names == ("sklearn_x",)


def test_override_table_is_used_when_the_distribution_is_absent() -> None:
    assert ExtrasBackendDenylist.import_names("scikit-learn", {}) == ("sklearn",)
    assert ExtrasBackendDenylist.import_names("beautifulsoup4", {}) == ("bs4",)
    assert ExtrasBackendDenylist.import_names("opencv-python", {}) == ("cv2",)
    assert ExtrasBackendDenylist.import_names("pyyaml", {}) == ("yaml",)


def test_normalised_name_is_the_fallback_for_a_plain_distribution() -> None:
    assert ExtrasBackendDenylist.import_names("qdrant-client", {}) == ("qdrant_client",)
