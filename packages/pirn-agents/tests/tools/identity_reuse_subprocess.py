"""Run an address-reuse regression loop in a clean subprocess (PIR-852)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


class IdentityReuseSubprocess:
    """Launch a reuse-loop worker script and return its JSON tally.

    Address reuse depends on allocator state. Inside a large, coverage-traced
    test process it can vanish entirely, which makes an in-process loop's
    ``reuses > 0`` precondition fail (or, if it were a skip, test nothing). A
    fresh interpreter restores the conditions production code runs under.
    Coverage's subprocess hooks are stripped, so the worker is not traced.
    """

    #: Environment variables through which coverage and pytest-cov start
    #: tracing inside child processes.
    _coverage_env_prefixes: tuple[str, ...] = ("COV_CORE_", "COVERAGE_")

    @staticmethod
    def run(scenario: str, iterations: int) -> dict[str, int]:
        """Run the sibling ``_identity_reuse_worker.py`` for ``scenario``.

        Args:
            scenario: Scenario name the worker dispatches on.
            iterations: Loop iterations to run.

        Returns:
            The worker's ``{"iterations", "reuses", "collisions"}`` tally.

        Raises:
            RuntimeError: If the worker exits non-zero.
        """
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(IdentityReuseSubprocess._coverage_env_prefixes)
        }
        # The same import roots as this process, so the worker tests this
        # checkout's code rather than whatever is installed.
        env["PYTHONPATH"] = os.pathsep.join(entry for entry in sys.path if entry)
        worker = Path(__file__).with_name("_identity_reuse_worker.py")
        completed = subprocess.run(
            [sys.executable, str(worker), scenario, str(iterations)],
            capture_output=True,
            text=True,
            env=env,
            timeout=50,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"reuse worker {scenario!r} failed ({completed.returncode}):\n{completed.stderr}"
            )
        return json.loads(completed.stdout.strip().splitlines()[-1])
