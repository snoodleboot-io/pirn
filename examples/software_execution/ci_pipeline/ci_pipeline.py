"""Example: CI/CD pipeline with fan-out, conditional steps, and audit trail.

Models a typical software release flow:
  checkout → lint + typecheck (parallel) → test (parallel by suite)
           → build → deploy

Demonstrates:
- True parallel execution (lint and typecheck run concurrently)
- Conditional short-circuit (build blocked if tests fail)
- Parameterised runs (same tapestry for every branch/commit)
- SQLite-backed lineage for audit trail

Run with:
    uv run python -m examples.software_execution.ci_pipeline
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.software_execution.ci_pipeline.deploy_receipt import DeployReceipt
from examples.software_execution.ci_pipeline.knots import (
    build_image,
    checkout,
    deploy,
    run_integration_tests,
    run_lint,
    run_typecheck,
    run_unit_tests,
)


class CiPipeline:
    """Builds and runs the CI/CD tapestry for one commit."""

    _run_parameters: ClassVar[dict[str, str]] = {
        "branch": "main",
        "commit_sha": "abc123def456",
        "environment": "staging",
    }

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire checkout → lint/typecheck → tests → build → deploy."""
        with Tapestry(history=history) as t:
            branch = Parameter("branch", str, _config=KnotConfig(id="branch"))
            sha = Parameter("commit_sha", str, _config=KnotConfig(id="sha"))
            env = Parameter("environment", str, _config=KnotConfig(id="env"))

            source = checkout(branch=branch, commit_sha=sha, _config=KnotConfig(id="checkout"))
            lint = run_lint(source=source, _config=KnotConfig(id="lint"))
            tc = run_typecheck(source=source, _config=KnotConfig(id="typecheck"))
            unit = run_unit_tests(source=source, lint=lint, _config=KnotConfig(id="unit_tests"))
            integ = run_integration_tests(
                source=source, tc=tc, _config=KnotConfig(id="integ_tests")
            )
            art = build_image(
                source=source, unit=unit, integration=integ, _config=KnotConfig(id="build")
            )
            deploy(artifact=art, environment=env, _config=KnotConfig(id="deploy"))
        return t

    @classmethod
    async def main(cls) -> None:
        """Run the pipeline once and print its lineage."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        result = await t.run(RunRequest(parameters=dict(cls._run_parameters)))

        duration = (result.finished_at - result.started_at).total_seconds()
        print(f"Run {'succeeded' if result.succeeded else 'FAILED'} in {duration:.2f}s\n")

        for rec in result.lineage:
            icon = "✓" if rec.outcome == "ok" else ("-" if rec.outcome == "skipped" else "✗")
            print(f"  {icon} {rec.knot_id:<20} {rec.outcome}")

        if result.succeeded:
            receipt: DeployReceipt = result.outputs["deploy"]
            print(f"\nDeployed {receipt.image_tag} → {receipt.environment}")
