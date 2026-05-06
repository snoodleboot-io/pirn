"""Unit tests for CronTrigger."""

from __future__ import annotations

import unittest
from datetime import time
from unittest.mock import patch

from pirn.core.run_request import RunRequest
from pirn.triggers.cron import CronTrigger


class TestCronTriggerConstruction(unittest.TestCase):
    def test_rejects_neither_mode(self) -> None:
        with self.assertRaisesRegex(TypeError, "every_seconds"):
            CronTrigger()

    def test_rejects_both_modes(self) -> None:
        with self.assertRaisesRegex(TypeError, "not both"):
            CronTrigger(every_seconds=5, at_times=[time(9, 0)])

    def test_name(self) -> None:
        t = CronTrigger(every_seconds=60)
        self.assertEqual(t.name, "CronTrigger")

    def test_close_sets_flag(self) -> None:
        import asyncio
        t = CronTrigger(every_seconds=1)
        asyncio.run(t.close())
        self.assertTrue(t._closed)


class TestCronTriggerStream(unittest.IsolatedAsyncioTestCase):
    async def test_every_seconds_emits_up_to_max_runs(self) -> None:
        with patch("pirn.triggers.cron.asyncio.sleep", return_value=None):
            trigger = CronTrigger(every_seconds=0.001, max_runs=3)
            requests = []
            async for req in trigger.stream():
                requests.append(req)
            self.assertEqual(len(requests), 3)
            self.assertIsInstance(requests[0], RunRequest)

    async def test_parameters_factory_called(self) -> None:
        call_count = [0]

        def factory():
            call_count[0] += 1
            return {"ts": call_count[0]}

        with patch("pirn.triggers.cron.asyncio.sleep", return_value=None):
            trigger = CronTrigger(every_seconds=0.001, parameters_factory=factory, max_runs=2)
            reqs = []
            async for req in trigger.stream():
                reqs.append(req)
        self.assertEqual(call_count[0], 2)
        self.assertEqual(reqs[0].parameters["ts"], 1)

    async def test_empty_parameters_without_factory(self) -> None:
        with patch("pirn.triggers.cron.asyncio.sleep", return_value=None):
            trigger = CronTrigger(every_seconds=0.001, max_runs=1)
            async for req in trigger.stream():
                self.assertEqual(req.parameters, {})
