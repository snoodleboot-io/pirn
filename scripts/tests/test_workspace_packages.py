"""Tests for the workspace package graph CI uses (PIR-872)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workspace_packages import WorkspacePackages, WorkspacePackagesCli  # noqa: E402

_REPO = Path(__file__).resolve().parents[2]
_ALL = [
    "pirn-agents",
    "pirn-core",
    "pirn-data",
    "pirn-health",
    "pirn-ml",
    "pirn-oilgas",
    "pirn-signal",
]


@pytest.fixture
def workspace() -> WorkspacePackages:
    return WorkspacePackages(_REPO)


class TestGraph:
    def test_reads_all_seven_packages(self, workspace: WorkspacePackages) -> None:
        assert workspace.names() == _ALL

    def test_closures_follow_the_declared_edges(
        self, workspace: WorkspacePackages
    ) -> None:
        assert workspace.closure("pirn-core") == ["pirn-core"]
        assert workspace.closure("pirn-ml") == ["pirn-core", "pirn-data", "pirn-ml"]
        assert workspace.closure("pirn-ml", include_self=False) == [
            "pirn-core",
            "pirn-data",
        ]
        assert workspace.closure("pirn-signal") == ["pirn-core", "pirn-signal"]

    def test_test_extras_drop_heavy_and_pirn_pulling_extras(
        self, workspace: WorkspacePackages
    ) -> None:
        extras = workspace.test_extras("pirn-core")
        assert "all-domains" not in extras
        assert "tensorflow" not in extras
        assert "sqlite" in extras


class TestAffected:
    def test_a_diff_touching_every_package_affects_every_package(
        self, workspace: WorkspacePackages
    ) -> None:
        # The PR #368 shape: a large diff whose shared-path and early package matches
        # a `printf | grep -q` pipeline under pipefail silently dropped.
        changed = [
            f"packages/{p}/{p.replace('-', '_')}/m{i}.py"
            for p in _ALL
            for i in range(3000)
        ]
        assert workspace.affected(changed) == _ALL

    def test_core_change_affects_every_dependent(
        self, workspace: WorkspacePackages
    ) -> None:
        assert workspace.affected(["packages/pirn-core/pirn/core/knot.py"]) == _ALL

    def test_data_change_affects_data_and_ml_only(
        self, workspace: WorkspacePackages
    ) -> None:
        assert workspace.affected(["packages/pirn-data/pyproject.toml"]) == [
            "pirn-data",
            "pirn-ml",
        ]

    def test_leaf_change_affects_only_that_package(
        self, workspace: WorkspacePackages
    ) -> None:
        assert workspace.affected(["packages/pirn-signal/tests/test_x.py"]) == [
            "pirn-signal"
        ]

    @pytest.mark.parametrize(
        "path", [".github/workflows/workspace.yml", "scripts/check_conventions.py"]
    )
    def test_shared_tooling_affects_everything(
        self, workspace: WorkspacePackages, path: str
    ) -> None:
        assert workspace.affected(["docs/index.md", path]) == _ALL

    def test_empty_diff_affects_everything(self, workspace: WorkspacePackages) -> None:
        assert workspace.affected([]) == _ALL

    def test_docs_only_change_affects_nothing(
        self, workspace: WorkspacePackages
    ) -> None:
        assert workspace.affected(["docs/index.md", "README.md"]) == []


class TestCli:
    def test_affected_writes_github_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        changed = tmp_path / "changed.txt"
        changed.write_text("packages/pirn-data/pirn_data/data_batch.py\n")
        output = tmp_path / "out"

        code = WorkspacePackagesCli.main(
            [
                "affected",
                "--changed-file",
                str(changed),
                "--github-output",
                str(output),
            ],
            _REPO,
        )

        assert code == 0
        assert 'packages=["pirn-data", "pirn-ml"]' in output.read_text()
        assert "any=true" in output.read_text()
        assert json.dumps(["pirn-data", "pirn-ml"]) in capsys.readouterr().out

    def test_affected_fails_when_a_touched_package_is_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        changed = tmp_path / "changed.txt"
        changed.write_text("packages/pirn-agents/pirn_agents/x.py\n")
        monkeypatch.setattr(
            WorkspacePackages, "affected", lambda _self, _changed: ["pirn-core"]
        )

        assert (
            WorkspacePackagesCli.main(
                ["affected", "--changed-file", str(changed)], _REPO
            )
            == 1
        )

    def test_closure_wheels_selects_this_builds_versions(
        self,
        tmp_path: Path,
        workspace: WorkspacePackages,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        version = workspace.version("pirn-core")
        for stem, ver in (
            ("pirn_core", version),
            ("pirn_core", "99.0.0"),
            ("pirn_ml", version),
            ("pirn_data", version),
        ):
            (tmp_path / f"{stem}-{ver}-py3-none-any.whl").write_text("")

        code = WorkspacePackagesCli.main(
            ["closure-wheels", "pirn-ml", "--dist", str(tmp_path)], _REPO
        )

        printed = capsys.readouterr().out.split()
        assert code == 0
        assert sorted(Path(p).name for p in printed) == sorted(
            f"{stem}-{version}-py3-none-any.whl"
            for stem in ("pirn_core", "pirn_data", "pirn_ml")
        )

    def test_closure_wheels_fails_on_a_missing_wheel(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="pirn_core"):
            WorkspacePackagesCli.main(
                ["closure-wheels", "pirn-signal", "--dist", str(tmp_path)], _REPO
            )


class TestWorkflowWiring:
    """The two PR #368 CI defects must not come back."""

    @staticmethod
    def _code_lines() -> list[str]:
        text = (_REPO / ".github/workflows/workspace.yml").read_text(encoding="utf-8")
        return [
            line.strip()
            for line in text.splitlines()
            if not line.strip().startswith("#")
        ]

    def test_change_detection_uses_the_script_not_a_grep_pipeline(self) -> None:
        lines = self._code_lines()
        assert any("workspace_packages.py affected" in line for line in lines)
        assert [line for line in lines if "grep -q" in line] == []

    def test_no_workspace_job_installs_a_pirn_package_by_bare_name(self) -> None:
        bare = {*_ALL, "${{ matrix.package }}"}
        by_name = [
            line
            for line in self._code_lines()
            if "uv pip install" in line
            and "closure-wheels" not in line
            and (
                '"${{ matrix.package }}"' in line
                or any(token.strip("\"'") in bare for token in line.split())
            )
        ]
        assert by_name == []
