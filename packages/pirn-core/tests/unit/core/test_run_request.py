from __future__ import annotations

import unittest
from datetime import datetime

from pydantic import ValidationError

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.run_request import RunRequest


class TestRunRequest(unittest.TestCase):
    def test_default_construction(self) -> None:
        req = RunRequest()
        self.assertTrue(req.run_id.startswith("run-"))
        self.assertEqual(req.parameters, {})
        self.assertIsInstance(req.submitted_at, datetime)

    def test_run_id_auto_generated_unique(self) -> None:
        a = RunRequest()
        b = RunRequest()
        self.assertNotEqual(a.run_id, b.run_id)

    def test_explicit_run_id(self) -> None:
        req = RunRequest(run_id="my-run")
        self.assertEqual(req.run_id, "my-run")

    def test_parameters_stored(self) -> None:
        req = RunRequest(parameters={"x": 1, "y": "hello"})
        self.assertEqual(req.parameters["x"], 1)
        self.assertEqual(req.parameters["y"], "hello")

    def test_submitted_at_is_utc(self) -> None:
        req = RunRequest()
        self.assertIsNotNone(req.submitted_at.tzinfo)

    def test_frozen(self) -> None:
        req = RunRequest()
        with self.assertRaises(ValidationError):
            req.run_id = "other"


class TestRunRequestConcurrency(unittest.TestCase):
    def test_defaults_to_none(self) -> None:
        self.assertIsNone(RunRequest().concurrency)

    def test_carries_limits(self) -> None:
        # Arrange
        limits = ConcurrencyLimits(max_in_flight=8, groups={"api": 4})

        # Act
        req = RunRequest(concurrency=limits)

        # Assert
        self.assertEqual(req.concurrency, limits)

    def test_builds_limits_from_a_plain_mapping(self) -> None:
        # Arrange: a webhook or queue trigger hands over decoded JSON.
        payload = {"concurrency": {"max_in_flight": 2, "groups": {"api": 1}}}

        # Act
        req = RunRequest.model_validate(payload)

        # Assert
        assert req.concurrency is not None
        self.assertEqual(req.concurrency.max_in_flight, 2)
        self.assertEqual(req.concurrency.group_limit("api"), 1)

    def test_rejects_invalid_limits(self) -> None:
        with self.assertRaises(ValidationError):
            RunRequest.model_validate({"concurrency": {"max_in_flight": 0}})
