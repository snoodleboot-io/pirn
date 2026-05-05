from __future__ import annotations

import unittest
from datetime import datetime, UTC


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
        with self.assertRaises(Exception):
            req.run_id = "other"
