"""Round-trip and validation tests for :class:`JoblibFormat`.

Covers the security contract: construction MUST refuse to emit/load
unsigned payloads unless the caller passes ``allow_unsigned=True``.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("joblib")

from pirn.backends._signer import _Signer
from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.joblib_format import JoblibFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestJoblibFormatConstruction:
    def test_unsigned_construction_refused(self) -> None:
        with pytest.raises(ValueError):
            JoblibFormat()

    def test_unsigned_explicit_acknowledged(self) -> None:
        fmt = JoblibFormat(allow_unsigned=True)
        assert fmt.signed is False

    def test_signer_construction_ok(self) -> None:
        fmt = JoblibFormat(signer=_Signer.test_signer())
        assert fmt.signed is True

    def test_non_bool_allow_unsigned_rejected(self) -> None:
        with pytest.raises(TypeError):
            JoblibFormat(allow_unsigned="yes")  # type: ignore[arg-type]


class TestJoblibFormatBasics:
    def test_name(self) -> None:
        assert JoblibFormat(allow_unsigned=True).name == "joblib"

    def test_streaming_property(self) -> None:
        assert JoblibFormat(allow_unsigned=True).streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(
            JoblibFormat(allow_unsigned=True), BatchFileFormat
        )


class TestJoblibFormatRoundTripUnsigned:
    @pytest.mark.asyncio
    async def test_round_trip_basic_unsigned(self) -> None:
        fmt = JoblibFormat(allow_unsigned=True)
        payload_object = {"params": [1, 2, 3], "name": "demo"}
        body = await FormatRoundTrip.encode(
            fmt, [{"object": payload_object}]
        )
        decoded = await FormatRoundTrip.decode(fmt, body)
        assert len(decoded) == 1
        record: dict[str, Any] = dict(decoded[0])
        assert record["object"] == payload_object
        assert record["object_type"] == "dict"

    @pytest.mark.asyncio
    async def test_encode_empty_records_rejected(self) -> None:
        fmt = JoblibFormat(allow_unsigned=True)
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    @pytest.mark.asyncio
    async def test_encode_missing_object_key(self) -> None:
        fmt = JoblibFormat(allow_unsigned=True)
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"wrong": 1}])


class TestJoblibFormatRoundTripSigned:
    @pytest.mark.asyncio
    async def test_round_trip_signed(self) -> None:
        signer = _Signer.test_signer()
        fmt = JoblibFormat(signer=signer)
        body = await FormatRoundTrip.encode(
            fmt, [{"object": {"a": 1, "b": "two"}}]
        )
        # Signed payload begins with a 32-byte HMAC header.
        assert len(body) > 32
        decoded = await FormatRoundTrip.decode(fmt, body)
        assert decoded[0]["object"] == {"a": 1, "b": "two"}
        assert decoded[0]["object_type"] == "dict"

    @pytest.mark.asyncio
    async def test_signed_payload_rejected_when_tampered(self) -> None:
        signer = _Signer.test_signer()
        fmt = JoblibFormat(signer=signer)
        body = await FormatRoundTrip.encode(
            fmt, [{"object": [1, 2, 3]}]
        )
        # Flip a byte in the body section (after the 32-byte signature).
        tampered = bytearray(body)
        tampered[40] = tampered[40] ^ 0xFF
        with pytest.raises(ValueError):
            await FormatRoundTrip.decode(fmt, bytes(tampered))

    @pytest.mark.asyncio
    async def test_signed_payload_rejected_by_unsigned_reader(self) -> None:
        signer = _Signer.test_signer()
        writer = JoblibFormat(signer=signer)
        body = await FormatRoundTrip.encode(
            writer, [{"object": {"x": 1}}]
        )
        reader = JoblibFormat(allow_unsigned=True)
        # The signature header is not pickle, so unsigned read fails.
        with pytest.raises(ValueError):
            await FormatRoundTrip.decode(reader, body)
