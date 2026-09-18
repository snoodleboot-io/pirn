"""Tests for the workspace package graph CI uses (PIR-872)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workspace_packages import WorkspacePackages
from workspace_packages_cli import WorkspacePackagesCli

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
# Diffs that touch no packages/<pkg>/ tree: before PIR-873 each of these produced
# `affected: []` -> `any=false` -> every gate job skipped -> ci-status green.
_WORKSPACE_ONLY = [
    "examples/foo.py",
    "docs/bar.md",
    "Dockerfile.ci",
    ".pre-commit-config.yaml",
    "README.md",
    "packages/README.md",
]
# The jobs that must run on EVERY pull request — they scan the whole repository and
# are not fanned out over the affected packages.
_ALWAYS_RUN_JOBS = [
    "build-wheelhouse",
    "import-graph",
    "import-forwarding",
    "version-lockstep",
    "workspace-gates",
]


@pytest.fixture
def workspace() -> WorkspacePackages:
    return WorkspacePackages(_REPO)


class TestGraph:
    def test_reads_all_seven_packages(self, workspace: WorkspacePackages) -> None:
        assert workspace.names() == _ALL

    def test_closures_follow_the_declared_edges(self, workspace: WorkspacePackages) -> None:
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
        changed = [f"packages/{p}/{p.replace('-', '_')}/m{i}.py" for p in _ALL for i in range(3000)]
        assert workspace.affected(changed) == _ALL

    def test_core_change_affects_every_dependent(self, workspace: WorkspacePackages) -> None:
        assert workspace.affected(["packages/pirn-core/pirn/core/knot.py"]) == _ALL

    def test_data_change_affects_data_and_ml_only(self, workspace: WorkspacePackages) -> None:
        assert workspace.affected(["packages/pirn-data/pyproject.toml"]) == [
            "pirn-data",
            "pirn-ml",
        ]

    def test_leaf_change_affects_only_that_package(self, workspace: WorkspacePackages) -> None:
        assert workspace.affected(["packages/pirn-signal/tests/test_x.py"]) == ["pirn-signal"]

    @pytest.mark.parametrize(
        "path", [".github/workflows/workspace.yml", "scripts/check_conventions.py"]
    )
    def test_shared_tooling_affects_everything(
        self, workspace: WorkspacePackages, path: str
    ) -> None:
        assert workspace.affected(["docs/index.md", path]) == _ALL

    def test_empty_diff_affects_everything(self, workspace: WorkspacePackages) -> None:
        assert workspace.affected([]) == _ALL
        assert workspace.scope([]) == "all-packages"

    def test_docs_only_change_affects_no_package(self, workspace: WorkspacePackages) -> None:
        assert workspace.affected(["docs/index.md", "README.md"]) == []


class TestWorkspaceOnlyScope:
    """A diff that touches no package tree must still mean "run the workspace gates"."""

    @pytest.mark.parametrize("path", _WORKSPACE_ONLY)
    def test_a_change_outside_every_package_tree_is_workspace_only(
        self, workspace: WorkspacePackages, path: str
    ) -> None:
        assert workspace.scope([path]) == "workspace-only"
        assert workspace.affected([path]) == []

    @pytest.mark.parametrize("path", _WORKSPACE_ONLY)
    def test_workspace_only_outputs_signal_the_always_run_gates(
        self, workspace: WorkspacePackages, path: str
    ) -> None:
        outputs = workspace.change_outputs([path])

        assert outputs == {
            "packages": "[]",
            "any": "false",
            "workspace_only": "true",
            "scope": "workspace-only",
        }

    def test_a_package_change_is_never_workspace_only(self, workspace: WorkspacePackages) -> None:
        outputs = workspace.change_outputs(["docs/x.md", "packages/pirn-signal/pirn_signal/a.py"])

        assert outputs["scope"] == "affected-packages"
        assert outputs["workspace_only"] == "false"
        assert outputs["any"] == "true"

    def test_shared_tooling_is_all_packages_not_workspace_only(
        self, workspace: WorkspacePackages
    ) -> None:
        outputs = workspace.change_outputs(["scripts/workspace_packages.py"])

        assert outputs["scope"] == "all-packages"
        assert outputs["workspace_only"] == "false"
        assert json.loads(outputs["packages"]) == _ALL


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
        written = output.read_text()
        assert 'packages=["pirn-data", "pirn-ml"]' in written
        assert "any=true" in written
        assert "workspace_only=false" in written
        assert "scope=affected-packages" in written
        assert json.dumps(["pirn-data", "pirn-ml"]) in capsys.readouterr().out

    @pytest.mark.parametrize("path", _WORKSPACE_ONLY)
    def test_affected_writes_a_workspace_only_signal_not_a_bare_empty_list(
        self, tmp_path: Path, path: str
    ) -> None:
        # The PIR-873 hole: these diffs wrote only `packages=[]` + `any=false`, which
        # skipped every gate job and left ci-status green with nothing having run.
        changed = tmp_path / "changed.txt"
        changed.write_text(f"{path}\n")
        output = tmp_path / "out"

        code = WorkspacePackagesCli.main(
            ["affected", "--changed-file", str(changed), "--github-output", str(output)],
            _REPO,
        )

        assert code == 0
        assert sorted(output.read_text().splitlines()) == sorted(
            [
                "packages=[]",
                "any=false",
                "workspace_only=true",
                "scope=workspace-only",
            ]
        )

    def test_affected_fails_on_an_empty_set_that_is_not_workspace_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No package affected AND no workspace-only scope would mean "run nothing".
        changed = tmp_path / "changed.txt"
        changed.write_text("docs/index.md\n")
        monkeypatch.setattr(WorkspacePackages, "scope", lambda _self, _changed: "affected-packages")
        output = tmp_path / "out"

        code = WorkspacePackagesCli.main(
            ["affected", "--changed-file", str(changed), "--github-output", str(output)],
            _REPO,
        )

        assert code == 1
        assert not output.exists()

    def test_affected_fails_when_a_touched_package_is_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        changed = tmp_path / "changed.txt"
        changed.write_text("packages/pirn-agents/pirn_agents/x.py\n")
        monkeypatch.setattr(WorkspacePackages, "affected", lambda _self, _changed: ["pirn-core"])

        assert WorkspacePackagesCli.main(["affected", "--changed-file", str(changed)], _REPO) == 1

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
            f"{stem}-{version}-py3-none-any.whl" for stem in ("pirn_core", "pirn_data", "pirn_ml")
        )

    def test_closure_wheels_fails_on_a_missing_wheel(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="pirn_core"):
            WorkspacePackagesCli.main(
                ["closure-wheels", "pirn-signal", "--dist", str(tmp_path)], _REPO
            )


class TestWorkflowWiring:
    """The PR #368 and PIR-873 CI defects must not come back."""

    @staticmethod
    def _code_lines() -> list[str]:
        text = (_REPO / ".github/workflows/workspace.yml").read_text(encoding="utf-8")
        return [line.strip() for line in text.splitlines() if not line.strip().startswith("#")]

    @staticmethod
    def _job_blocks() -> dict[str, list[str]]:
        """Each job's own lines (comments stripped), keyed by job id."""
        text = (_REPO / ".github/workflows/workspace.yml").read_text(encoding="utf-8")
        lines = text.splitlines()
        start = lines.index("jobs:")
        header = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
        blocks: dict[str, list[str]] = {}
        current: str | None = None
        for line in lines[start + 1 :]:
            match = header.match(line)
            if match is not None:
                current = match.group(1)
                blocks[current] = []
            elif current is not None and not line.strip().startswith("#"):
                blocks[current].append(line.strip())
        return blocks

    @pytest.mark.parametrize("job", _ALWAYS_RUN_JOBS)
    def test_always_run_gates_are_not_gated_on_change_detection(self, job: str) -> None:
        # PIR-873: an examples/ or docs/ only PR made `any` false, every one of these
        # skipped, and a skipped job is not a failure — the PR merged with zero checks.
        blocks = self._job_blocks()

        assert job in blocks, f"{job} is missing from workspace.yml"
        assert [line for line in blocks[job] if "needs.changes.outputs.any" in line] == []

    def test_per_package_matrices_still_fan_out_over_the_affected_set_only(self) -> None:
        blocks = self._job_blocks()
        for job in (
            "lint",
            "test",
            "slow-tests",
            "install-isolation",
            "agents-extras-install",
            "unified",
        ):
            assert any("needs.changes.outputs.any == 'true'" in line for line in blocks[job]), job

    def test_ci_status_fails_on_a_skipped_always_run_gate(self) -> None:
        block = "\n".join(self._job_blocks()["ci-status"])
        for job in _ALWAYS_RUN_JOBS:
            assert f"needs.{job}.result" in block, job
        # Anything but `success` — `skipped` included — must fail the aggregator.
        assert 'if [ "$result" != "success" ]; then' in block
        assert "skipped required gate is a failure" in block

    def test_doc_import_gate_runs_on_every_pull_request(self) -> None:
        block = "\n".join(self._job_blocks()["workspace-gates"])

        assert "check_doc_imports.py" in block
        assert "AGENTIC_USE.md AGENTIC_USE_SPEC.md README.md docs examples/README.md" in block
        assert "continue-on-error" not in block

    def test_scripts_and_examples_are_ruff_checked_from_inside_the_tree(self) -> None:
        block = self._job_blocks()["workspace-gates"]
        # Ruff's first-party classification is cwd-relative and neither tree has a root
        # config, so the checks must cd in (the same reason the `lint` job cds in).
        for tree in ("scripts", "examples"):
            assert f"cd {tree}" in block, tree
        assert any("ruff check ." in line for line in block)
        assert any("ruff format --check ." in line for line in block)
        assert any("ruff==0.15.22" in line for line in block)

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
