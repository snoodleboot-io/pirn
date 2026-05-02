"""Round-trip and validation tests for :class:`MatlabMatFormat`.

Note: MAT-file v5 does not preserve Python ``bool`` (it becomes
``uint8``) or distinguish int widths beyond what scipy infers. Round-
trip tests therefore use ``int``, ``float``, and ``str`` fields only.
"""

from __future__ import annotations

import pytest

pytest.importorskip("scipy")
pytest.importorskip("scipy.io")
pytest.importorskip("numpy")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.matlab_mat_format import (
    MatlabMatFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestMatlabMatFormatConstruction:
    def test_default_arguments(self) -> None:
        fmt = MatlabMatFormat()
        assert fmt.variable_name == "data"
        assert fmt.field_names is None

    def test_custom_variable_name(self) -> None:
        fmt = MatlabMatFormat(variable_name="payload")
        assert fmt.variable_name == "payload"

    def test_empty_variable_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            MatlabMatFormat(variable_name="")

    def test_non_string_variable_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            MatlabMatFormat(variable_name=42)  # type: ignore[arg-type]

    def test_invalid_field_names_type(self) -> None:
        with pytest.raises(TypeError):
            MatlabMatFormat(field_names="ab")  # type: ignore[arg-type]

    def test_empty_field_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            MatlabMatFormat(field_names=("a", ""))


class TestMatlabMatFormatBasics:
    def test_name(self) -> None:
        assert MatlabMatFormat().name == "matlab-mat"

    def test_streaming_property(self) -> None:
        assert MatlabMatFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(MatlabMatFormat(), BatchFileFormat)


class TestMatlabMatFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5},
            {"id": 2, "name": "beta", "score": 2.25},
            {"id": 3, "name": "gamma", "score": 3.75},
        ]
        fmt = MatlabMatFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = MatlabMatFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_custom_variable_name(self) -> None:
        records = [{"id": 1, "label": "alpha"}]
        fmt = MatlabMatFormat(variable_name="payload")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_empty_payload_rejected(self) -> None:
        fmt = MatlabMatFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    @pytest.mark.asyncio
    async def test_decode_unknown_variable_raises(self) -> None:
        records = [{"id": 1, "label": "x"}]
        writer = MatlabMatFormat(variable_name="data")
        payload = await FormatRoundTrip.encode(writer, records)
        reader = MatlabMatFormat(variable_name="missing")
        with pytest.raises(ValueError):
            await FormatRoundTrip.decode(reader, payload)
