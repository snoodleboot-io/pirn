"""FITS and SEG-Y refuse rather than silently lose data (PIR-873).

Both formats used to swallow the awkward cases:

* ``FitsFormat`` decode turned an unreadable HDU array into ``data: None``,
  which is also how it reports "this HDU has no data", so the loss was
  invisible and the record round-tripped back out short.
* ``FitsFormat`` encode dropped any header card ``astropy`` would not accept.
* ``SegyFormat`` encode substituted zeros for a non-bytes payload, zero-padded a
  short trace and truncated a long one, and dropped any trace-header field it
  could not coerce — writing a file that looked valid and was not the data
  handed in.

The validation now lives in helpers that need neither ``astropy`` nor
``segyio``, so these are real tests on a stock install rather than a module
skipped for a missing extra — which is how the swallows survived the first
audit.
"""

from __future__ import annotations

import struct
import unittest
from typing import Any

import numpy as np

from pirn.connectors.file_formats.fits_format import FitsFormat
from pirn.connectors.file_formats.segy_format import SegyFormat


class _UnreadableArray:
    """An HDU array whose bytes cannot be produced (a memory-mapped truncation)."""

    def tobytes(self) -> bytes:
        raise ValueError("buffer is smaller than requested size")


class _Hdu:
    def __init__(self, data: Any) -> None:
        self.data = data


class TestFitsDecodeDataLoss(unittest.TestCase):
    def test_an_hdu_with_no_data_reports_none(self) -> None:
        assert FitsFormat._hdu_data_bytes(0, _Hdu(None)) is None

    def test_readable_data_comes_back_as_bytes(self) -> None:
        array = np.arange(4, dtype=np.uint8)
        assert FitsFormat._hdu_data_bytes(0, _Hdu(array)) == array.tobytes()

    def test_unreadable_data_raises_instead_of_looking_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "HDU 3 has data that cannot be read as bytes"):
            FitsFormat._hdu_data_bytes(3, _Hdu(_UnreadableArray()))


class TestFitsEncodeHeaderCards(unittest.TestCase):
    def test_structural_keywords_are_left_to_astropy(self) -> None:
        cards = FitsFormat._writable_header_cards(
            0, {"SIMPLE": True, "EXTEND": True, "END": None, "XTENSION": "IMAGE", "OBJECT": "M31"}
        )
        assert cards == [("OBJECT", "M31")]

    def test_ordinary_cards_are_kept_in_order(self) -> None:
        cards = FitsFormat._writable_header_cards(0, {"NAXIS": 1, "OBJECT": "M31", "EXPTIME": 12.5})
        assert cards == [("NAXIS", 1), ("OBJECT", "M31"), ("EXPTIME", 12.5)]

    def test_a_non_string_keyword_raises_instead_of_being_dropped(self) -> None:
        with self.assertRaisesRegex(TypeError, "record 2 header key must be str"):
            FitsFormat._writable_header_cards(2, {7: "not a keyword"})


def _trace(samples: list[float]) -> bytes:
    return struct.pack(f">{len(samples)}f", *samples)


class TestSegyTraceSamples(unittest.TestCase):
    def test_a_matching_trace_decodes_to_its_samples(self) -> None:
        payload = _trace([1.0, 2.0, 3.0])
        samples = SegyFormat._trace_samples(0, {"data": payload}, 3)
        assert samples.tolist() == [1.0, 2.0, 3.0]
        assert samples.dtype == np.float32

    def test_a_short_trace_raises_instead_of_being_zero_padded(self) -> None:
        with self.assertRaisesRegex(ValueError, r"trace 1 holds 2 samples but the file .* 4 per"):
            SegyFormat._trace_samples(1, {"data": _trace([1.0, 2.0])}, 4)

    def test_a_long_trace_raises_instead_of_being_truncated(self) -> None:
        with self.assertRaisesRegex(ValueError, r"trace 2 holds 5 samples"):
            SegyFormat._trace_samples(2, {"data": _trace([1.0, 2.0, 3.0, 4.0, 5.0])}, 3)

    def test_a_missing_trace_raises_instead_of_writing_zeros(self) -> None:
        with self.assertRaisesRegex(ValueError, r"trace 0 holds 0 samples"):
            SegyFormat._trace_samples(0, {}, 3)

    def test_a_non_bytes_payload_raises_instead_of_writing_zeros(self) -> None:
        with self.assertRaisesRegex(TypeError, "trace 0 'data' must be bytes, got list"):
            SegyFormat._trace_samples(0, {"data": [1.0, 2.0]}, 2)

    def test_a_partial_sample_raises_instead_of_being_dropped(self) -> None:
        with self.assertRaisesRegex(ValueError, "9 bytes, which is not a whole number"):
            SegyFormat._trace_samples(0, {"data": _trace([1.0, 2.0]) + b"\x00"}, 2)


class TestSegyHeaderUpdates(unittest.TestCase):
    def test_no_header_means_no_updates(self) -> None:
        assert SegyFormat._header_updates(0, {}) == {}

    def test_integer_fields_pass_through(self) -> None:
        assert SegyFormat._header_updates(0, {"header": {"iline": 3, "xline": 7}}) == {
            "iline": 3,
            "xline": 7,
        }

    def test_a_numeric_string_is_still_accepted(self) -> None:
        assert SegyFormat._header_updates(0, {"header": {"iline": "42"}}) == {"iline": 42}

    def test_an_uncoercible_field_raises_instead_of_being_dropped(self) -> None:
        with self.assertRaisesRegex(ValueError, r"trace 4 header field 'iline' cannot be read"):
            SegyFormat._header_updates(4, {"header": {"iline": "north"}})

    def test_a_non_numeric_field_raises_instead_of_being_dropped(self) -> None:
        with self.assertRaisesRegex(ValueError, r"trace 0 header field 'iline' cannot be read"):
            SegyFormat._header_updates(0, {"header": {"iline": object()}})

    def test_a_non_mapping_header_raises_instead_of_being_ignored(self) -> None:
        with self.assertRaisesRegex(TypeError, "trace 0 'header' must be a mapping, got list"):
            SegyFormat._header_updates(0, {"header": [("iline", 3)]})
