"""Unit tests for LogEmitter."""

from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock, patch

from pirn.emitters.log import LogEmitter


def _make_status_event(knot_id: str = "k1", run_id: str = "r1") -> MagicMock:
    event = MagicMock()
    event.knot_id = knot_id
    event.run_id = run_id
    event.state = MagicMock()
    event.state.value = "running"
    event.detail = {}
    return event


def _make_lineage_record() -> MagicMock:
    record = MagicMock()
    record.run_id = "r1"
    record.knot_id = "k1"
    record.outcome = "ok"
    record.output_hash = "abc123"
    record.duration_ms = 42.0
    record.error_record_id = None
    record.skip_reason = None
    record.started_at = MagicMock()
    record.finished_at = MagicMock()
    record.model_dump_json = MagicMock(return_value='{"run_id":"r1"}')
    return record


def _make_run_result(succeeded: bool = True) -> MagicMock:
    result = MagicMock()
    result.run_id = "r1"
    result.succeeded = succeeded
    result.dispatcher = "local"
    result.duration_seconds = 0.5
    result.started_at = MagicMock()
    result.finished_at = MagicMock()
    result.model_dump_json = MagicMock(return_value='{"run_id":"r1"}')
    return result


class TestLogEmitterConstruction(unittest.TestCase):
    def test_uses_provided_logger(self) -> None:
        logger = logging.getLogger("test_logger")
        emitter = LogEmitter(logger=logger)
        self.assertIs(emitter._log, logger)

    def test_uses_default_logger_when_none(self) -> None:
        emitter = LogEmitter()
        self.assertEqual(emitter._log.name, "pirn")

    def test_with_payload_flag(self) -> None:
        emitter = LogEmitter(with_payload=True)
        self.assertTrue(emitter._with_payload)


class TestLogEmitterEvents(unittest.IsolatedAsyncioTestCase):
    async def test_on_status_logs_info(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        emitter = LogEmitter(logger=logger)
        await emitter.on_status(_make_status_event())
        logger.info.assert_called_once()

    async def test_on_lineage_logs_info(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        emitter = LogEmitter(logger=logger)
        await emitter.on_lineage(_make_lineage_record())
        logger.info.assert_called_once()

    async def test_on_run_result_success_logs_info(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        emitter = LogEmitter(logger=logger)
        await emitter.on_run_result(_make_run_result(succeeded=True))
        logger.log.assert_called_once()
        args = logger.log.call_args[0]
        self.assertEqual(args[0], logging.INFO)

    async def test_on_run_result_failure_logs_error(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        emitter = LogEmitter(logger=logger)
        await emitter.on_run_result(_make_run_result(succeeded=False))
        args = logger.log.call_args[0]
        self.assertEqual(args[0], logging.ERROR)

    async def test_on_lineage_includes_payload_when_requested(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        emitter = LogEmitter(logger=logger, with_payload=True)
        record = _make_lineage_record()
        await emitter.on_lineage(record)
        _, kwargs = logger.info.call_args
        self.assertIn("pirn_payload", kwargs.get("extra", {}))
