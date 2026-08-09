"""Unit tests for CronTrigger."""

from __future__ import annotations

import unittest
from datetime import time
from unittest.mock import patch

from pirn.core.run_request import RunRequest
from pirn.triggers.cron import CronTrigger


class _SleepRecorder:
    """Async sleep double that records every requested delay and never waits."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


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


class TestCronTriggerTrailingSleep(unittest.IsolatedAsyncioTestCase):
    """PIR-790: the generator must not sleep a final interval past ``max_runs``."""

    async def test_no_trailing_sleep_after_final_fire(self) -> None:
        recorder = _SleepRecorder()
        # Patch the module-level asyncio.sleep so this test also expresses the
        # defect against the pre-fix implementation, which had no injection seam.
        with patch("pirn.triggers.cron.asyncio.sleep", new=recorder):
            trigger = CronTrigger(every_seconds=1.0, max_runs=2)
            fired: list[RunRequest] = []
            async for req in trigger.stream():
                fired.append(req)

        self.assertEqual(len(fired), 2)
        # Fires land at t=0 and t=1; the generator must exit at t=1, not t=2.
        self.assertEqual(recorder.delays, [1.0])

    async def test_single_run_sleeps_not_at_all(self) -> None:
        recorder = _SleepRecorder()
        with patch("pirn.triggers.cron.asyncio.sleep", new=recorder):
            trigger = CronTrigger(every_seconds=5.0, max_runs=1)
            fired = [req async for req in trigger.stream()]

        self.assertEqual(len(fired), 1)
        self.assertEqual(recorder.delays, [])

    async def test_at_times_mode_has_no_trailing_sleep(self) -> None:
        recorder = _SleepRecorder()
        with patch("pirn.triggers.cron.asyncio.sleep", new=recorder):
            trigger = CronTrigger(at_times=[time(9, 0)], max_runs=2)
            fired = [req async for req in trigger.stream()]

        # at-times mode sleeps *before* each fire, so one sleep per fire.
        self.assertEqual(len(fired), 2)
        self.assertEqual(len(recorder.delays), 2)


class TestCronTriggerSleepInjection(unittest.IsolatedAsyncioTestCase):
    """PIR-790: ``sleep=`` is the seam downstream schedulers inject."""

    async def test_injected_sleep_receives_interval_delays(self) -> None:
        recorder = _SleepRecorder()
        trigger = CronTrigger(every_seconds=2.5, max_runs=3, sleep=recorder)
        fired = [req async for req in trigger.stream()]

        self.assertEqual(len(fired), 3)
        self.assertEqual(recorder.delays, [2.5, 2.5])

    async def test_injected_sleep_takes_precedence_over_module_sleep(self) -> None:
        recorder = _SleepRecorder()
        module_sleep = _SleepRecorder()
        with patch("pirn.triggers.cron.asyncio.sleep", new=module_sleep):
            trigger = CronTrigger(every_seconds=1.0, max_runs=2, sleep=recorder)
            _ = [req async for req in trigger.stream()]

        self.assertEqual(recorder.delays, [1.0])
        self.assertEqual(module_sleep.delays, [])

    async def test_first_fire_is_still_immediate(self) -> None:
        recorder = _SleepRecorder()
        trigger = CronTrigger(every_seconds=30.0, max_runs=2, sleep=recorder)
        agen = trigger.stream()
        first = await anext(agen)

        self.assertIsInstance(first, RunRequest)
        # Nothing was slept before the first fire — interval mode fires at t=0.
        self.assertEqual(recorder.delays, [])
        await agen.aclose()


class TestCronTriggerDelayFn(unittest.IsolatedAsyncioTestCase):
    """PIR-790: ``delay_fn(ordinal) -> float`` is the per-fire schedule seam."""

    async def test_delay_fn_drives_each_fire(self) -> None:
        recorder = _SleepRecorder()
        trigger = CronTrigger(delay_fn=lambda n: n * 0.5, max_runs=3, sleep=recorder)
        fired = [req async for req in trigger.stream()]

        self.assertEqual(len(fired), 3)
        self.assertEqual(recorder.delays, [0.5, 1.0, 1.5])

    async def test_delay_fn_receives_one_based_ordinals(self) -> None:
        seen: list[int] = []

        def schedule(ordinal: int) -> float:
            seen.append(ordinal)
            return 0.0

        trigger = CronTrigger(delay_fn=schedule, max_runs=4, sleep=_SleepRecorder())
        _ = [req async for req in trigger.stream()]

        self.assertEqual(seen, [1, 2, 3, 4])

    async def test_delay_fn_composes_with_parameters_factory(self) -> None:
        trigger = CronTrigger(
            delay_fn=lambda n: 0.0,
            parameters_factory=lambda: {"k": "v"},
            max_runs=2,
            sleep=_SleepRecorder(),
        )
        fired = [req async for req in trigger.stream()]

        self.assertEqual([r.parameters for r in fired], [{"k": "v"}, {"k": "v"}])


class TestCronTriggerValidation(unittest.TestCase):
    """PIR-790: construction-time validation of ``max_runs`` and mode selection."""

    def test_rejects_non_positive_max_runs(self) -> None:
        for bad in (0, -1, -100):
            with self.subTest(max_runs=bad):
                with self.assertRaisesRegex(ValueError, "max_runs"):
                    CronTrigger(every_seconds=1.0, max_runs=bad)

    def test_rejects_non_integer_max_runs(self) -> None:
        for bad in (1.5, "3", True):
            with self.subTest(max_runs=bad):
                with self.assertRaisesRegex(ValueError, "max_runs"):
                    CronTrigger(every_seconds=1.0, max_runs=bad)  # type: ignore[arg-type]

    def test_accepts_positive_max_runs_and_none(self) -> None:
        CronTrigger(every_seconds=1.0, max_runs=1)
        CronTrigger(every_seconds=1.0, max_runs=None)

    def test_rejects_delay_fn_with_every_seconds(self) -> None:
        with self.assertRaises(TypeError):
            CronTrigger(every_seconds=1.0, delay_fn=lambda n: 1.0)

    def test_rejects_delay_fn_with_at_times(self) -> None:
        with self.assertRaises(TypeError):
            CronTrigger(at_times=[time(9, 0)], delay_fn=lambda n: 1.0)

    def test_no_mode_error_mentions_delay_fn(self) -> None:
        with self.assertRaisesRegex(TypeError, "delay_fn"):
            CronTrigger()

    def test_delay_fn_alone_is_a_valid_mode(self) -> None:
        trigger = CronTrigger(delay_fn=lambda n: 1.0)
        self.assertEqual(trigger.name, "CronTrigger")


class TestCronTriggerClose(unittest.IsolatedAsyncioTestCase):
    """``close()`` stops the stream after the in-flight sleep, with no further fire."""

    async def test_close_during_sleep_yields_nothing_further(self) -> None:
        trigger = CronTrigger(every_seconds=1.0, sleep=_SleepRecorder())
        fired: list[RunRequest] = []
        async for req in trigger.stream():
            fired.append(req)
            if len(fired) == 2:
                await trigger.close()

        self.assertEqual(len(fired), 2)

    async def test_close_during_at_times_sleep_yields_nothing_further(self) -> None:
        trigger = CronTrigger(at_times=[time(9, 0)], sleep=_SleepRecorder())
        fired: list[RunRequest] = []
        async for req in trigger.stream():
            fired.append(req)
            if len(fired) == 2:
                await trigger.close()

        self.assertEqual(len(fired), 2)
