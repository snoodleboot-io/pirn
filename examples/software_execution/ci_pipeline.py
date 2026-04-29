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
    uv run python examples/software_execution/ci_pipeline.py
"""

import asyncio
import time
from dataclasses import dataclass

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn.backends.sqlite.sqlite_history import SQLiteHistory

# ----------------------------------------------------------------- models


@dataclass
class CheckoutResult:
    commit_sha: str
    branch: str
    files_changed: int


@dataclass
class QualityReport:
    tool: str
    issues: int
    duration_ms: float


@dataclass
class TestReport:
    suite: str
    passed: int
    failed: int
    duration_ms: float


@dataclass
class BuildArtifact:
    image_tag: str
    size_bytes: int


@dataclass
class DeployReceipt:
    environment: str
    image_tag: str
    deployed_at: float


# ----------------------------------------------------------------- knots


@knot
async def checkout(branch: str, commit_sha: str) -> CheckoutResult:
    """Clone the repo at the given commit."""
    await asyncio.sleep(0.05)
    return CheckoutResult(commit_sha=commit_sha, branch=branch, files_changed=42)


@knot
async def run_lint(source: CheckoutResult) -> QualityReport:
    t0 = time.monotonic()
    await asyncio.sleep(0.03)
    return QualityReport("ruff", issues=0, duration_ms=(time.monotonic() - t0) * 1000)


@knot
async def run_typecheck(source: CheckoutResult) -> QualityReport:
    t0 = time.monotonic()
    await asyncio.sleep(0.04)
    return QualityReport("pyright", issues=0, duration_ms=(time.monotonic() - t0) * 1000)


@knot
async def run_unit_tests(source: CheckoutResult, lint: QualityReport) -> TestReport:
    if lint.issues > 0:
        raise RuntimeError(f"unit tests blocked: {lint.issues} lint issue(s)")
    t0 = time.monotonic()
    await asyncio.sleep(0.06)
    return TestReport("unit", passed=334, failed=0, duration_ms=(time.monotonic() - t0) * 1000)


@knot
async def run_integration_tests(source: CheckoutResult, tc: QualityReport) -> TestReport:
    if tc.issues > 0:
        raise RuntimeError(f"integration tests blocked: {tc.issues} type error(s)")
    t0 = time.monotonic()
    await asyncio.sleep(0.08)
    elapsed_ms = (time.monotonic() - t0) * 1000
    return TestReport("integration", passed=48, failed=0, duration_ms=elapsed_ms)


@knot
async def build_image(
    source: CheckoutResult,
    unit: TestReport,
    integration: TestReport,
) -> BuildArtifact:
    if unit.failed > 0 or integration.failed > 0:
        raise RuntimeError("build blocked: test failures")
    await asyncio.sleep(0.1)
    return BuildArtifact(
        image_tag=f"myapp:{source.commit_sha[:8]}",
        size_bytes=180_000_000,
    )


@knot
async def deploy(artifact: BuildArtifact, environment: str) -> DeployReceipt:
    await asyncio.sleep(0.05)
    return DeployReceipt(
        environment=environment,
        image_tag=artifact.image_tag,
        deployed_at=time.time(),
    )


# ----------------------------------------------------------------- wiring


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        branch = Parameter("branch", str, _config=KnotConfig(id="branch"))
        sha = Parameter("commit_sha", str, _config=KnotConfig(id="sha"))
        env = Parameter("environment", str, _config=KnotConfig(id="env"))

        source = checkout(branch=branch, commit_sha=sha, _config=KnotConfig(id="checkout"))
        lint = run_lint(source=source, _config=KnotConfig(id="lint"))
        tc = run_typecheck(source=source, _config=KnotConfig(id="typecheck"))
        unit = run_unit_tests(source=source, lint=lint, _config=KnotConfig(id="unit_tests"))
        integ = run_integration_tests(source=source, tc=tc, _config=KnotConfig(id="integ_tests"))
        art = build_image(
            source=source, unit=unit, integration=integ, _config=KnotConfig(id="build")
        )
        deploy(artifact=art, environment=env, _config=KnotConfig(id="deploy"))
    return t


# ----------------------------------------------------------------- main


async def main() -> None:
    history = SQLiteHistory()
    t = build_tapestry(history=history)

    result = await t.run(
        RunRequest(
            parameters={
                "branch": "main",
                "commit_sha": "abc123def456",
                "environment": "staging",
            }
        )
    )

    duration = (result.finished_at - result.started_at).total_seconds()
    print(f"Run {'succeeded' if result.succeeded else 'FAILED'} in {duration:.2f}s\n")

    for rec in result.lineage:
        icon = "✓" if rec.outcome == "ok" else ("-" if rec.outcome == "skipped" else "✗")
        print(f"  {icon} {rec.knot_id:<20} {rec.outcome}")

    if result.succeeded:
        receipt: DeployReceipt = result.outputs["deploy"]
        print(f"\nDeployed {receipt.image_tag} → {receipt.environment}")


if __name__ == "__main__":
    asyncio.run(main())
