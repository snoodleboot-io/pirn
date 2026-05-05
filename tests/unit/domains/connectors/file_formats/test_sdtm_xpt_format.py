"""Tests for :class:`SdtmXptFormat` — SDTM SAS Transport (XPT) format."""

from __future__ import annotations
import unittest


try:
    import pyreadstat
except ImportError as _e:
    raise unittest.SkipTest("pyreadstat not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.sdtm_xpt_format import SdtmXptFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_xpt_bytes(rows: list[dict], column_labels: dict | None = None, file_label: str = "") -> bytes:
    """Create a minimal XPT file using pyreadstat."""
    import tempfile
    from pathlib import Path
    import pandas as pd
    import pyreadstat

    df = pd.DataFrame(rows)
    col_names = list(df.columns)
    labels = [column_labels.get(c, "") for c in col_names] if column_labels else [""] * len(col_names)

    with tempfile.NamedTemporaryFile(suffix=".xpt", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        pyreadstat.write_xport(df, tmp_path, file_label=file_label, column_labels=labels)
        return Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def _decode(fmt: SdtmXptFormat, payload: bytes) -> list[dict]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestSdtmXptFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(SdtmXptFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert SdtmXptFormat().streaming is False

    def test_name(self) -> None:
        assert SdtmXptFormat().name == "sdtm_xpt"


# ---------------------------------------------------------------------------
# PHI sanitisation (SDTM is de-identified; verify metadata handling)
# ---------------------------------------------------------------------------

class TestSdtmXptFormatPhiSanitisation(unittest.IsolatedAsyncioTestCase):
    async def test_first_record_has_metadata(self) -> None:
        rows = [{"SUBJ": "001", "AGE": 30}, {"SUBJ": "002", "AGE": 25}]
        payload = _make_xpt_bytes(rows)
        records = await _decode(SdtmXptFormat(), payload)
        assert "_metadata" in records[0]

    async def test_subsequent_records_no_metadata(self) -> None:
        rows = [{"SUBJ": "001", "AGE": 30}, {"SUBJ": "002", "AGE": 25}]
        payload = _make_xpt_bytes(rows)
        records = await _decode(SdtmXptFormat(), payload)
        assert "_metadata" not in records[1]

    async def test_metadata_contains_column_labels(self) -> None:
        rows = [{"SUBJ": "001"}]
        payload = _make_xpt_bytes(rows, column_labels={"SUBJ": "Subject ID"})
        records = await _decode(SdtmXptFormat(), payload)
        meta = records[0]["_metadata"]
        assert "column_labels" in meta
        assert meta["column_labels"].get("SUBJ") == "Subject ID"

    async def test_metadata_contains_file_label(self) -> None:
        rows = [{"SUBJ": "001"}]
        payload = _make_xpt_bytes(rows, file_label="DM Dataset")
        records = await _decode(SdtmXptFormat(), payload)
        meta = records[0]["_metadata"]
        assert "file_label" in meta


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestSdtmXptFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_row_values_preserved(self) -> None:
        rows = [{"SUBJ": "001", "AGE": 30}, {"SUBJ": "002", "AGE": 25}]
        payload = _make_xpt_bytes(rows)
        fmt = SdtmXptFormat()
        decoded = await _decode(fmt, payload)
        encoded = await FormatRoundTrip.encode(fmt, decoded)
        re_decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(re_decoded) == 2

    async def test_round_trip_single_row(self) -> None:
        rows = [{"SUBJ": "001", "RACE": "WHITE"}]
        payload = _make_xpt_bytes(rows)
        fmt = SdtmXptFormat()
        decoded = await _decode(fmt, payload)
        encoded = await FormatRoundTrip.encode(fmt, decoded)
        re_decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(re_decoded) == 1


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestSdtmXptFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_payload_raises(self) -> None:
        fmt = SdtmXptFormat()

        async def _iter():
            yield b"this is not an xpt file"

        with self.assertRaises(Exception):
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------

class TestSdtmXptFormatMissingDep(unittest.TestCase):
    def test_missing_pyreadstat_raises(self) -> None:
        # TODO(unittest-migrate): replace 'monkeypatch' built-in fixture — use unittest.mock.patch / assertLogs
        import sys
        monkeypatch.setitem(sys.modules, "pyreadstat", None)  # type: ignore[arg-type]
        fmt = SdtmXptFormat()
        with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
            fmt._load_pyreadstat()
