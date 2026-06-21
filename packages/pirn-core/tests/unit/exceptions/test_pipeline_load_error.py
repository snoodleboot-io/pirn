from __future__ import annotations

import unittest

from pirn.exceptions.pipeline_load_error import PipelineLoadError
from pirn.exceptions.pirn_error import PirnError


class TestPipelineLoadError(unittest.TestCase):
    def test_is_pirn_error(self):
        self.assertTrue(issubclass(PipelineLoadError, PirnError))

    def test_raise_and_catch_as_pirn_error(self):
        with self.assertRaises(PirnError):
            raise PipelineLoadError("bad yaml")

    def test_message_preserved(self):
        err = PipelineLoadError("could not resolve knot")
        self.assertEqual(str(err), "could not resolve knot")

    def test_raise_and_catch_specific(self):
        with self.assertRaises(PipelineLoadError):
            raise PipelineLoadError("x")
