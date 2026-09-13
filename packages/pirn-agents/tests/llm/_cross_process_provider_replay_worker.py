"""Worker process for the two-interpreter LLM provider record/replay test (PIR-840).

Run as a script, never imported by the suite::

    python _cross_process_provider_replay_worker.py <record|replay> <workdir> <scenario>...

Every provider in this worker talks to a local mock HTTP server started by the parent
test, whose base URL arrives in ``PIRN_MOCK_LLM_URL``; no vendor is ever contacted.
Each scenario builds its own tapestry over ``SQLiteHistory(<workdir>/<scenario>/h.db)``
and ``LocalDiskDataStore(<workdir>/<scenario>/values)``. ``record`` runs it and stores
the run id; ``replay`` loads that run in *this* process and runs the same graph, with
the replay-side provider configuration, under ``replay=``. The worker prints one JSON
object mapping each scenario to its outcome.

A scenario is ``<vendor>__<case>``: the vendor picks the provider class (every case
runs against each wire format equally) and the case picks what differs on replay.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, ClassVar

from pirn.backends.local_disk_data_store import LocalDiskDataStore
from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.recording.replay_error import ReplayError
from pirn.recording.replay_session import ReplaySession
from pirn.security.credential_ref import CredentialRef
from pirn.tapestry import Tapestry

from pirn_agents.llm.anthropic_messages_provider import AnthropicMessagesProvider
from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from tests.llm.asks_model import AsksModel


class ProviderReplayWorker:
    """Build, record and replay one provider scenario per call."""

    #: Provider class per vendor label. Both wire formats run every case.
    vendors: ClassVar[dict[str, type[BaseLLMProvider]]] = {
        "openai_compatible": OpenAICompatibleProvider,
        "anthropic_messages": AnthropicMessagesProvider,
    }

    def __init__(self, *, mode: str, workdir: Path, mock_url: str) -> None:
        self._mode = mode
        self._workdir = workdir
        self._mock_url = mock_url

    def provider(self, scenario: str) -> BaseLLMProvider:
        """Return the provider for ``scenario`` as configured in this process's mode."""
        vendor, case = scenario.split("__", 1)
        replaying = self._mode == "replay"
        model = "model-a"
        key = "sk-RECORD-SENTINEL"
        base_url = f"{self._mock_url}/v1"
        if case == "same_config":
            pass
        elif case == "different_model":
            model = "model-b" if replaying else model
        elif case == "different_key":
            key = "sk-REPLAY-SENTINEL" if replaying else key
        elif case == "query_url":
            base_url = f"{base_url}?api-version=2024-01-01"
        else:
            raise SystemExit(f"unknown case {case!r}")
        return self.vendors[vendor](
            model=model, base_url=base_url, credential=CredentialRef(secret=key)
        )

    async def run(self, scenario: str) -> dict[str, Any]:
        """Record or replay ``scenario`` and return a JSON-friendly summary."""
        scenario_dir = self._workdir / scenario
        scenario_dir.mkdir(parents=True, exist_ok=True)
        provider = self.provider(scenario)
        tapestry = Tapestry(
            history=SQLiteHistory(path=str(scenario_dir / "h.db")),
            data_store=LocalDiskDataStore(scenario_dir / "values", allow_unsigned=True),
        )
        with tapestry:
            AsksModel(llm=provider, _config=KnotConfig(id="ask"))
        run_id_file = scenario_dir / "run_id"
        try:
            if self._mode == "record":
                result = await tapestry.run(RunRequest())
                run_id_file.write_text(result.run_id)
                return {"outcome": "RECORDED", "output": result.outputs["ask"]}
            session = await ReplaySession.from_history(
                history=tapestry.history, run_id=run_id_file.read_text()
            )
            try:
                result = await tapestry.run(RunRequest(), replay=session)
            except ReplayError as exc:
                return {"outcome": "REFUSED", "error": type(exc).__name__}
            return {"outcome": "SERVED", "output": result.outputs["ask"]}
        finally:
            await provider.close()


async def main(argv: list[str]) -> None:
    """Entry point: ``<mode> <workdir> <scenario>...``."""
    mode, workdir, *scenarios = argv
    worker = ProviderReplayWorker(
        mode=mode, workdir=Path(workdir), mock_url=os.environ["PIRN_MOCK_LLM_URL"]
    )
    summary = {scenario: await worker.run(scenario) for scenario in scenarios}
    print(json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
