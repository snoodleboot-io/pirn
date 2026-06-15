"""Tests for :class:`Hl7v2Format` — HL7 v2 message format."""

from __future__ import annotations

import unittest

try:
    import hl7  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("hl7 not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.hl7v2_format import Hl7v2Format

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_HL7 = (
    "MSH|^~\\&|LABSYS|HOSP|EHR|CLINIC|20230601120000||ORU^R01|CTRL001|P|2.5\r"
    "PID|1||P001^^^HOSP^MR||Doe^Jane^A||19900101|F|||123 Main St^^Boston^MA^02134||||\r"
    "OBR|1||ORD001|CBC^Complete Blood Count|||20230601110000\r"
)


async def _decode(fmt: Hl7v2Format, payload: bytes) -> list[dict]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestHl7v2FormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(Hl7v2Format(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert Hl7v2Format().streaming is False

    def test_name(self) -> None:
        assert Hl7v2Format().name == "hl7v2"


# ---------------------------------------------------------------------------
# PHI sanitisation
# ---------------------------------------------------------------------------

class TestHl7v2FormatPhiSanitisation(unittest.IsolatedAsyncioTestCase):
    async def test_pid5_name_redacted(self) -> None:
        records = await _decode(Hl7v2Format(), _MINIMAL_HL7.encode("utf-8"))
        pid_seg = next(
            s for s in records[0]["segments"] if s["segment_id"] == "PID"
        )
        # PID.5 is index 4 in fields (0-based, field 5 - 1)
        assert pid_seg["fields"][4] == "[REDACTED]"

    async def test_pid7_dob_redacted(self) -> None:
        records = await _decode(Hl7v2Format(), _MINIMAL_HL7.encode("utf-8"))
        pid_seg = next(
            s for s in records[0]["segments"] if s["segment_id"] == "PID"
        )
        # PID.7 is index 6 in fields (0-based)
        assert pid_seg["fields"][6] == "[REDACTED]"

    async def test_pid11_address_redacted(self) -> None:
        records = await _decode(Hl7v2Format(), _MINIMAL_HL7.encode("utf-8"))
        pid_seg = next(
            s for s in records[0]["segments"] if s["segment_id"] == "PID"
        )
        # PID.11 is index 10 in fields (0-based)
        assert pid_seg["fields"][10] == "[REDACTED]"

    async def test_phi_keywords_frozenset(self) -> None:
        assert isinstance(Hl7v2Format._phi_keywords, frozenset)

    async def test_record_shape(self) -> None:
        records = await _decode(Hl7v2Format(), _MINIMAL_HL7.encode("utf-8"))
        assert len(records) == 1
        record = records[0]
        assert "message_type" in record
        assert "message_control_id" in record
        assert "sending_facility" in record
        assert "receiving_facility" in record
        assert "segments" in record

    async def test_message_control_id(self) -> None:
        records = await _decode(Hl7v2Format(), _MINIMAL_HL7.encode("utf-8"))
        assert records[0]["message_control_id"] == "CTRL001"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestHl7v2FormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_preserves_segments(self) -> None:
        fmt = Hl7v2Format()
        payload = _MINIMAL_HL7.encode("utf-8")
        decoded = await _decode(fmt, payload)
        encoded = await FormatRoundTrip.encode(fmt, decoded)
        re_decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(re_decoded) == 1
        orig_seg_ids = [s["segment_id"] for s in decoded[0]["segments"]]
        re_seg_ids = [s["segment_id"] for s in re_decoded[0]["segments"]]
        assert orig_seg_ids == re_seg_ids

    async def test_round_trip_two_messages(self) -> None:
        second = _MINIMAL_HL7.replace("CTRL001", "CTRL002")
        two_msgs = (_MINIMAL_HL7 + second).encode("utf-8")
        fmt = Hl7v2Format()
        decoded = await _decode(fmt, two_msgs)
        assert len(decoded) == 2
        encoded = await FormatRoundTrip.encode(fmt, decoded)
        re_decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(re_decoded) == 2


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestHl7v2FormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_hl7_raises(self) -> None:
        fmt = Hl7v2Format()

        async def _iter():
            yield b"NOT|A|VALID|HL7|MESSAGE\r"

        with self.assertRaises(Exception):  # noqa: B017
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------

class TestHl7v2FormatMissingDep(unittest.TestCase):
    def test_missing_hl7_raises(self) -> None:
        import unittest.mock
        fmt = Hl7v2Format()
        with unittest.mock.patch.dict("sys.modules", {"hl7": None}):
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                fmt._load_hl7()
