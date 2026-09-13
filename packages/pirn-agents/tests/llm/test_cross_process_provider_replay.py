"""Two-interpreter record/replay of HTTP LLM provider calls (PIR-840 PR-3).

A run is recorded in one Python process and replayed in a **different** one, with
different ``PYTHONHASHSEED`` values, over a ``SQLiteHistory`` and a
``LocalDiskDataStore`` on disk. An in-process test cannot tell a content hash from an
identity token, because both are stable inside one interpreter; only a second
interpreter shows whether a provider's recorded calls can really be served.

The providers are real ``OpenAICompatibleProvider`` and ``AnthropicMessagesProvider``
instances making real HTTP requests to a loopback mock server owned by this test
(no vendor, no injected client, since an injected client is identity-keyed by
design). Every request the server receives is recorded, so "served from the
recording" is observed across the process boundary rather than inferred.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pytest

from tests.llm.mock_llm_http_server import MockLLMHttpServer


@pytest.mark.timeout(120)
class TestCrossProcessProviderReplay(unittest.TestCase):
    """Record in one interpreter, replay in another, per vendor and case."""

    vendors = ("openai_compatible", "anthropic_messages")
    cases = ("same_config", "different_model", "different_key", "query_url")
    #: Environment variables through which coverage and pytest-cov start tracing
    #: inside child processes; stripped so the workers run untraced and cannot race
    #: the parent's coverage data file.
    coverage_env_prefixes = ("COV_CORE_", "COVERAGE_")
    recorded: dict[str, Any]
    replayed: dict[str, Any]
    requests_after_record: list[str]
    requests_after_replay: list[str]

    @classmethod
    def scenarios(cls) -> tuple[str, ...]:
        return tuple(f"{vendor}__{case}" for vendor in cls.vendors for case in cls.cases)

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls._server = MockLLMHttpServer()
        cls._server.start()
        workdir = Path(cls._tmp.name)
        try:
            cls.recorded = cls._run_worker("record", workdir, hash_seed="11")
            cls.requests_after_record = list(cls._server.received)
            cls.replayed = cls._run_worker("replay", workdir, hash_seed="22")
            cls.requests_after_replay = list(cls._server.received)
        except BaseException:
            cls._server.stop()
            cls._tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.stop()
        cls._tmp.cleanup()

    @classmethod
    def _run_worker(cls, mode: str, workdir: Path, *, hash_seed: str) -> dict[str, Any]:
        """Run the worker in a fresh interpreter and return its JSON summary."""
        package_root = Path(__file__).resolve().parents[2]
        inherited = os.environ.get("PYTHONPATH")
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(cls.coverage_env_prefixes)
        }
        env.update(
            {
                "PYTHONHASHSEED": hash_seed,
                "PIRN_ALLOW_UNSIGNED": "1",
                "PIRN_MOCK_LLM_URL": cls._server.url,
                "PYTHONPATH": os.pathsep.join(
                    [str(package_root), *([inherited] if inherited else [])]
                ),
            }
        )
        # The mock server is on loopback; a configured proxy must not intercept it.
        env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
        worker = Path(__file__).with_name("_cross_process_provider_replay_worker.py")
        completed = subprocess.run(
            [sys.executable, str(worker), mode, str(workdir), *cls.scenarios()],
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

    def test_every_scenario_really_called_the_mock_server_while_recording(self) -> None:
        """Guards the other assertions: the request counts they compare against are real."""
        assert all(entry["outcome"] == "RECORDED" for entry in self.recorded.values())
        assert len(self.requests_after_record) == len(self.scenarios())
        for vendor in self.vendors:
            assert self.recorded[f"{vendor}__same_config"]["output"] == "reply from model-a"

    def test_no_provider_calls_the_model_again_during_replay(self) -> None:
        assert self.requests_after_replay == self.requests_after_record

    def test_the_same_configuration_is_served_from_the_recording(self) -> None:
        for vendor in self.vendors:
            with self.subTest(vendor=vendor):
                scenario = f"{vendor}__same_config"

                assert self.replayed[scenario] == {
                    "outcome": "SERVED",
                    "output": self.recorded[scenario]["output"],
                }

    def test_a_different_model_refuses_instead_of_serving(self) -> None:
        for vendor in self.vendors:
            with self.subTest(vendor=vendor):
                assert self.replayed[f"{vendor}__different_model"] == {
                    "outcome": "REFUSED",
                    "error": "ReplayMismatchError",
                }

    def test_a_different_api_key_is_served_because_a_secret_is_not_identity(self) -> None:
        for vendor in self.vendors:
            with self.subTest(vendor=vendor):
                scenario = f"{vendor}__different_key"

                assert self.replayed[scenario] == {
                    "outcome": "SERVED",
                    "output": self.recorded[scenario]["output"],
                }

    def test_a_base_url_with_a_query_string_stays_identity_keyed_and_refuses(self) -> None:
        for vendor in self.vendors:
            with self.subTest(vendor=vendor):
                assert self.replayed[f"{vendor}__query_url"] == {
                    "outcome": "REFUSED",
                    "error": "ReplayMismatchError",
                }

    def test_no_secret_reaches_the_recorded_history_or_values(self) -> None:
        workdir = Path(self._tmp.name)
        for path in workdir.rglob("*"):
            if path.is_file():
                with self.subTest(path=path.name):
                    data = path.read_bytes()

                    assert b"sk-RECORD-SENTINEL" not in data
                    assert b"sk-REPLAY-SENTINEL" not in data
