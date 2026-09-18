"""Knot factories for the ``examples.software_execution.ci_pipeline`` example."""

from __future__ import annotations

import asyncio
import time

from pirn.core.knot_factory import KnotFactory

from examples.software_execution.ci_pipeline.build_artifact import BuildArtifact
from examples.software_execution.ci_pipeline.checkout_result import CheckoutResult
from examples.software_execution.ci_pipeline.deploy_receipt import DeployReceipt
from examples.software_execution.ci_pipeline.quality_report import QualityReport
from examples.software_execution.ci_pipeline.test_report import TestReport


@KnotFactory.knot
async def checkout(branch: str, commit_sha: str) -> CheckoutResult:
    """Clone the repo at the given commit."""
    await asyncio.sleep(0.05)
    return CheckoutResult(commit_sha=commit_sha, branch=branch, files_changed=42)


@KnotFactory.knot
async def run_lint(source: CheckoutResult) -> QualityReport:
    t0 = time.monotonic()
    await asyncio.sleep(0.03)
    return QualityReport("ruff", issues=0, duration_ms=(time.monotonic() - t0) * 1000)


@KnotFactory.knot
async def run_typecheck(source: CheckoutResult) -> QualityReport:
    t0 = time.monotonic()
    await asyncio.sleep(0.04)
    return QualityReport("pyright", issues=0, duration_ms=(time.monotonic() - t0) * 1000)


@KnotFactory.knot
async def run_unit_tests(source: CheckoutResult, lint: QualityReport) -> TestReport:
    if lint.issues > 0:
        raise RuntimeError(f"unit tests blocked: {lint.issues} lint issue(s)")
    t0 = time.monotonic()
    await asyncio.sleep(0.06)
    return TestReport("unit", passed=334, failed=0, duration_ms=(time.monotonic() - t0) * 1000)


@KnotFactory.knot
async def run_integration_tests(source: CheckoutResult, tc: QualityReport) -> TestReport:
    if tc.issues > 0:
        raise RuntimeError(f"integration tests blocked: {tc.issues} type error(s)")
    t0 = time.monotonic()
    await asyncio.sleep(0.08)
    elapsed_ms = (time.monotonic() - t0) * 1000
    return TestReport("integration", passed=48, failed=0, duration_ms=elapsed_ms)


@KnotFactory.knot
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


@KnotFactory.knot
async def deploy(artifact: BuildArtifact, environment: str) -> DeployReceipt:
    await asyncio.sleep(0.05)
    return DeployReceipt(
        environment=environment,
        image_tag=artifact.image_tag,
        deployed_at=time.time(),
    )
