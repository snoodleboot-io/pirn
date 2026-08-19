"""Tests for KnotRegistrationNotice (run attribution on the wire)."""

from __future__ import annotations

import json
import unittest

from pirn.backends.base.knot_registration_notice import KnotRegistrationNotice
from pirn.tapestry import _current_run_id, current_run_id


class TestKnotRegistrationNoticeRoundTrip(unittest.TestCase):
    def test_encode_decode_preserves_both_fields(self) -> None:
        notice = KnotRegistrationNotice.decode(KnotRegistrationNotice("k1", "run-a").encode())
        self.assertEqual(notice.knot_id, "k1")
        self.assertEqual(notice.run_id, "run-a")

    def test_encode_decode_preserves_absent_run(self) -> None:
        notice = KnotRegistrationNotice.decode(KnotRegistrationNotice("k1", None).encode())
        self.assertEqual(notice.knot_id, "k1")
        self.assertIsNone(notice.run_id)

    def test_encoded_payload_is_json(self) -> None:
        payload = json.loads(KnotRegistrationNotice("k1", "run-a").encode())
        self.assertEqual(payload, {"knot_id": "k1", "run_id": "run-a"})


class TestKnotRegistrationNoticeForCurrentRun(unittest.TestCase):
    def test_stamps_the_ambient_run(self) -> None:
        token = _current_run_id.set("run-a")
        try:
            notice = KnotRegistrationNotice.for_current_run("k1")
        finally:
            _current_run_id.reset(token)
        self.assertEqual(notice.run_id, "run-a")

    def test_no_ambient_run_yields_none(self) -> None:
        self.assertIsNone(current_run_id())
        self.assertIsNone(KnotRegistrationNotice.for_current_run("k1").run_id)


class TestKnotRegistrationNoticeDecodeTolerance(unittest.TestCase):
    """Anything that is not a well-formed notice is a bare knot id.

    A publisher from before PIR-815 sends the knot id alone, so decoding
    has to accept it rather than lose the registration.
    """

    def test_legacy_bare_knot_id(self) -> None:
        notice = KnotRegistrationNotice.decode("k1")
        self.assertEqual(notice.knot_id, "k1")
        self.assertIsNone(notice.run_id)

    def test_knot_id_that_happens_to_be_valid_json_scalar(self) -> None:
        for raw in ("123", "null", "true", '"quoted"'):
            with self.subTest(raw=raw):
                notice = KnotRegistrationNotice.decode(raw)
                self.assertEqual(notice.knot_id, raw)
                self.assertIsNone(notice.run_id)

    def test_json_object_without_knot_id_is_a_bare_id(self) -> None:
        raw = '{"run_id": "run-a"}'
        notice = KnotRegistrationNotice.decode(raw)
        self.assertEqual(notice.knot_id, raw)
        self.assertIsNone(notice.run_id)

    def test_non_string_run_id_is_dropped(self) -> None:
        notice = KnotRegistrationNotice.decode('{"knot_id": "k1", "run_id": 7}')
        self.assertEqual(notice.knot_id, "k1")
        self.assertIsNone(notice.run_id)


class TestKnotRegistrationNoticeRunScope(unittest.TestCase):
    def test_binds_and_restores_run_identity(self) -> None:
        self.assertIsNone(current_run_id())
        with KnotRegistrationNotice("k1", "run-a").run_scope():
            self.assertEqual(current_run_id(), "run-a")
        self.assertIsNone(current_run_id())

    def test_unowned_notice_binds_no_run(self) -> None:
        token = _current_run_id.set("stale-run")
        try:
            with KnotRegistrationNotice("k1", None).run_scope():
                # Explicitly clears whatever the delivering task carried,
                # rather than letting it leak into the subscriber.
                self.assertIsNone(current_run_id())
            self.assertEqual(current_run_id(), "stale-run")
        finally:
            _current_run_id.reset(token)
