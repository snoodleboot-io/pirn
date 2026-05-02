"""Round-trip and validation tests for :class:`Hdf5Format`."""

from __future__ import annotations

import pytest

pytest.importorskip("h5py")
pytest.importorskip("numpy")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.hdf5_format import (
    Hdf5Format,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestHdf5FormatConstruction:
    def test_default_arguments(self) -> None:
        fmt = Hdf5Format()
        assert fmt.dataset_path == "/data"
        assert fmt.compression is None

    def test_custom_dataset_path_normalised(self) -> None:
        fmt = Hdf5Format(dataset_path="records")
        assert fmt.dataset_path == "/records"

    def test_absolute_dataset_path_preserved(self) -> None:
        fmt = Hdf5Format(dataset_path="/group/sub")
        assert fmt.dataset_path == "/group/sub"

    def test_empty_dataset_path_rejected(self) -> None:
        with pytest.raises(ValueError):
            Hdf5Format(dataset_path="")

    def test_non_string_dataset_path_rejected(self) -> None:
        with pytest.raises(ValueError):
            Hdf5Format(dataset_path=42)  # type: ignore[arg-type]

    def test_invalid_compression_value(self) -> None:
        with pytest.raises(ValueError):
            Hdf5Format(compression="brotli")

    def test_invalid_compression_type(self) -> None:
        with pytest.raises(TypeError):
            Hdf5Format(compression=123)  # type: ignore[arg-type]

    def test_valid_compression(self) -> None:
        fmt = Hdf5Format(compression="gzip")
        assert fmt.compression == "gzip"


class TestHdf5FormatBasics:
    def test_name(self) -> None:
        assert Hdf5Format().name == "hdf5"

    def test_streaming_property(self) -> None:
        assert Hdf5Format().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(Hdf5Format(), BatchFileFormat)


class TestHdf5FormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5, "active": True},
            {"id": 2, "name": "beta", "score": 2.25, "active": False},
            {"id": 3, "name": "gamma", "score": 3.75, "active": True},
        ]
        fmt = Hdf5Format()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = Hdf5Format()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_with_compression(self) -> None:
        records = [
            {"id": 1, "label": "x"},
            {"id": 2, "label": "y"},
        ]
        fmt = Hdf5Format(compression="gzip")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_custom_dataset_path(self) -> None:
        records = [{"id": 1, "name": "alpha"}]
        fmt = Hdf5Format(dataset_path="/custom/inner")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_empty_payload_rejected(self) -> None:
        # HDF5 structured arrays require at least one row to encode.
        fmt = Hdf5Format()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    @pytest.mark.asyncio
    async def test_decode_unknown_dataset_raises(self) -> None:
        records = [{"id": 1, "name": "alpha"}]
        writer = Hdf5Format(dataset_path="/data")
        payload = await FormatRoundTrip.encode(writer, records)
        reader = Hdf5Format(dataset_path="/missing")
        with pytest.raises(ValueError):
            await FormatRoundTrip.decode(reader, payload)
