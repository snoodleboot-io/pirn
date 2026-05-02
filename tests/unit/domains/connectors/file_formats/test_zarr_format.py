"""Round-trip and validation tests for :class:`ZarrFormat`."""

from __future__ import annotations

import pytest

pytest.importorskip("zarr")
pytest.importorskip("numpy")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.zarr_format import (
    ZarrFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

# Zarr v3 emits warnings about structured-dtype spec stability that are
# not relevant to round-trip semantics in pirn's usage. Apply via the
# ``filterwarnings`` mark so it sticks for every test in this module.
pytestmark = pytest.mark.filterwarnings(
    "ignore:.*does not have a Zarr V3 specification.*",
)


class TestZarrFormatConstruction:
    def test_default_arguments(self) -> None:
        fmt = ZarrFormat()
        assert fmt.dataset_path == "data"
        assert fmt.chunks is None
        assert fmt.field_names is None

    def test_custom_dataset_path(self) -> None:
        fmt = ZarrFormat(dataset_path="rows")
        assert fmt.dataset_path == "rows"

    def test_empty_dataset_path_rejected(self) -> None:
        with pytest.raises(ValueError):
            ZarrFormat(dataset_path="")

    def test_non_string_dataset_path_rejected(self) -> None:
        with pytest.raises(ValueError):
            ZarrFormat(dataset_path=42)  # type: ignore[arg-type]

    def test_invalid_chunks_type(self) -> None:
        with pytest.raises(TypeError):
            ZarrFormat(chunks=[10])  # type: ignore[arg-type]

    def test_negative_chunk_rejected(self) -> None:
        with pytest.raises(ValueError):
            ZarrFormat(chunks=(0,))

    def test_non_int_chunk_rejected(self) -> None:
        with pytest.raises(ValueError):
            ZarrFormat(chunks=(1.5,))  # type: ignore[arg-type]

    def test_invalid_field_names_type(self) -> None:
        with pytest.raises(TypeError):
            ZarrFormat(field_names="ab")  # type: ignore[arg-type]

    def test_empty_field_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            ZarrFormat(field_names=("a", ""))


class TestZarrFormatBasics:
    def test_name(self) -> None:
        assert ZarrFormat().name == "zarr"

    def test_streaming_property(self) -> None:
        assert ZarrFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(ZarrFormat(), BatchFileFormat)


class TestZarrFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5, "active": True},
            {"id": 2, "name": "beta", "score": 2.25, "active": False},
            {"id": 3, "name": "gamma", "score": 3.75, "active": True},
        ]
        fmt = ZarrFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = ZarrFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_custom_dataset_path(self) -> None:
        records = [{"id": 1, "label": "alpha"}]
        fmt = ZarrFormat(dataset_path="custom")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_with_chunks(self) -> None:
        records = [{"id": i, "value": float(i) * 0.5} for i in range(8)]
        fmt = ZarrFormat(chunks=(4,))
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_empty_payload_rejected(self) -> None:
        fmt = ZarrFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    @pytest.mark.asyncio
    async def test_decode_unknown_dataset_raises(self) -> None:
        records = [{"id": 1, "label": "x"}]
        writer = ZarrFormat(dataset_path="data")
        payload = await FormatRoundTrip.encode(writer, records)
        reader = ZarrFormat(dataset_path="missing")
        with pytest.raises(ValueError):
            await FormatRoundTrip.decode(reader, payload)
