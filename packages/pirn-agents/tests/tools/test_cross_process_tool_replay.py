"""Two-interpreter record/replay of tool calls (PIR-840).

A run is recorded in one Python process and replayed in a **different** one, with
different ``PYTHONHASHSEED`` values, over a ``SQLiteHistory`` and a
``LocalDiskDataStore`` on disk. This is the case identity-keyed tools could never
satisfy: an in-process test cannot tell a content hash from an ``id()`` token,
because both are stable inside one interpreter.

The work runs in :mod:`_cross_process_replay_worker`; every scenario is recorded in
one subprocess and replayed in a second, and each test method asserts on one
scenario's outcome. Real tool executions are appended to a log file, so "served
from the recording" is observed across the process boundary rather than inferred.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.timeout(120)
class TestCrossProcessToolReplay(unittest.TestCase):
    """Record in one interpreter, replay in another, per scenario."""

    scenarios = (
        "literal_call",
        "upstream_call",
        "tool_executor",
        "read_file_root_swap",
        "stateful_tool",
    )
    recorded: dict[str, Any]
    replayed: dict[str, Any]
    invocations_after_record: Counter[str]
    invocations_after_replay: Counter[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        workdir = Path(cls._tmp.name)
        cls.recorded = cls._run_worker("record", workdir, hash_seed="11")
        cls.invocations_after_record = cls._invocations(workdir)
        cls.replayed = cls._run_worker("replay", workdir, hash_seed="22")
        cls.invocations_after_replay = cls._invocations(workdir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @classmethod
    def _run_worker(cls, mode: str, workdir: Path, *, hash_seed: str) -> dict[str, Any]:
        """Run the worker in a fresh interpreter and return its JSON summary."""
        worker = Path(__file__).with_name("_cross_process_replay_worker.py")
        package_root = Path(__file__).resolve().parents[2]
        inherited = os.environ.get("PYTHONPATH")
        env = {
            **os.environ,
            "PYTHONHASHSEED": hash_seed,
            "PIRN_ALLOW_UNSIGNED": "1",
            "PIRN_REPLAY_WORKDIR": str(workdir),
            "PYTHONPATH": os.pathsep.join([str(package_root), *([inherited] if inherited else [])]),
        }
        completed = subprocess.run(
            [sys.executable, str(worker), mode, str(workdir), *cls.scenarios],
            capture_output=True,
            text=True,
            env=env,
            timeout=110,
            check=False,
        )
        assert completed.returncode == 0, (
            f"{mode} worker failed ({completed.returncode}):\n{completed.stderr}"
        )
        return json.loads(completed.stdout.strip().splitlines()[-1])

    @staticmethod
    def _invocations(workdir: Path) -> Counter[str]:
        """Count real tool executions logged by either process."""
        log = workdir / "invocations.log"
        return Counter(log.read_text().split()) if log.exists() else Counter()

    def test_the_two_interpreters_really_executed_each_tool_once_while_recording(self) -> None:
        """Guards the other assertions: the counts they compare against are real."""
        assert all(entry["outcome"] == "RECORDED" for entry in self.recorded.values())
        assert self.invocations_after_record == Counter({"add": 3, "tenant_add": 1})

    def test_no_tool_is_invoked_again_during_replay(self) -> None:
        assert self.invocations_after_replay == self.invocations_after_record

    def test_a_pure_tool_with_a_literal_call_is_served_from_the_recording(self) -> None:
        replay = self.replayed["literal_call"]

        assert replay["outcome"] == "SERVED"
        assert replay["output"] == self.recorded["literal_call"]["output"]
        assert replay["output"]["result"] == 3

    def test_a_pure_tool_with_an_upstream_call_is_served_from_the_recording(self) -> None:
        replay = self.replayed["upstream_call"]

        assert replay["outcome"] == "SERVED"
        assert replay["output"] == self.recorded["upstream_call"]["output"]

    def test_a_tool_executor_over_pure_tools_is_served_from_the_recording(self) -> None:
        replay = self.replayed["tool_executor"]

        assert replay["outcome"] == "SERVED"
        assert replay["output"] == self.recorded["tool_executor"]["output"]

    def test_a_file_tool_with_a_different_root_refuses_instead_of_serving(self) -> None:
        """Regression for the measured false match: root A must never be served as root B."""
        assert self.replayed["read_file_root_swap"] == {
            "outcome": "REFUSED",
            "error": "ReplayMismatchError",
        }

    def test_a_stateful_tool_without_a_canonical_state_stays_identity_keyed(self) -> None:
        assert self.replayed["stateful_tool"] == {
            "outcome": "REFUSED",
            "error": "ReplayMismatchError",
        }
