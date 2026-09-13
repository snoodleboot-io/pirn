"""Unit tests for :class:`SegyObjectStoreDisassembler`.

Includes regression coverage for the scratch-temp-file cleanup fix: ``segyio``
has no in-memory writer, so ``_encode`` round-trips through a
``NamedTemporaryFile`` and must remove it in every case, including when
``segyio`` raises.
"""

from __future__ import annotations

import glob
import os
import sys
import tempfile
import types
import unittest
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_oilgas.disassemblers.segy_object_store_disassembler import SegyObjectStoreDisassembler
from pirn_oilgas.types.segy_payload import SegyPayload
from pirn_oilgas.types.segy_volume import SegyVolume


def _payload_param() -> Parameter:
    return Parameter("payload", SegyPayload, _config=KnotConfig(id="payload"))


def _make() -> SegyObjectStoreDisassembler:
    return SegyObjectStoreDisassembler(
        payload=_payload_param(), _config=KnotConfig(id="disassembler")
    )


def _fake_payload() -> SegyPayload:
    traces = np.zeros((2, 4), dtype=np.float32)
    return SegyPayload(metadata=SegyVolume(volume_id="vol-01"), data=traces)


class _FakeSegyFile:
    """Stands in for the context manager ``segyio.create`` returns."""

    def __init__(self, path: str) -> None:
        self._path = path
        self.bin: dict[str, Any] = {}
        self.trace: dict[int, np.ndarray] = {}

    def __enter__(self) -> _FakeSegyFile:
        return self

    def __exit__(self, *exc_info: object) -> None:
        with open(self._path, "wb") as fh:
            fh.write(b"fake-segy-bytes")


class _FakeSpec:
    sorting: Any = None
    format: int = 0
    samples: Any = None
    tracecount: int = 0


class _FakeTraceSortingFormat:
    UNKNOWN_SORTING = 0


def _install_fake_segyio(monkeypatch: pytest.MonkeyPatch, create: Any) -> None:
    fake = types.ModuleType("segyio")
    fake.spec = _FakeSpec  # type: ignore[attr-defined]
    fake.TraceSortingFormat = _FakeTraceSortingFormat  # type: ignore[attr-defined]
    fake.create = create  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "segyio", fake)


def _segy_temp_files() -> set[str]:
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "*.segy")))


class TestEncodeTempFileCleanup:
    def test_removes_temp_file_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_segyio(monkeypatch, create=lambda path, spec: _FakeSegyFile(path))
        from pirn_oilgas.disassemblers.segy_object_store_disassembler import _encode

        before = _segy_temp_files()
        result = _encode(_fake_payload())

        assert result == b"fake-segy-bytes"
        assert _segy_temp_files() == before

    def test_removes_temp_file_when_segyio_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _broken_create(path: str, spec: Any) -> _FakeSegyFile:
            raise RuntimeError("segyio boom")

        _install_fake_segyio(monkeypatch, create=_broken_create)
        from pirn_oilgas.disassemblers.segy_object_store_disassembler import _encode

        before = _segy_temp_files()
        with pytest.raises(RuntimeError, match="segyio boom"):
            _encode(_fake_payload())

        assert _segy_temp_files() == before


class TestSegyObjectStoreDisassemblerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_bytes(self) -> None:
        knot = _make()
        with patch(
            "pirn_oilgas.disassemblers.segy_object_store_disassembler._encode",
            return_value=b"segy-bytes",
        ):
            result = await knot.process(payload=_fake_payload())
        assert result == b"segy-bytes"

    async def test_rejects_non_segy_payload(self) -> None:
        knot = _make()
        with self.assertRaisesRegex(TypeError, "SegyPayload"):
            await knot.process(payload="not-a-payload")  # type: ignore[arg-type]

    async def test_rejects_empty_traces(self) -> None:
        knot = _make()
        empty_payload = SegyPayload(
            metadata=SegyVolume(volume_id="vol-01"),
            data=np.zeros((0,), dtype=np.float32),
        )
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(payload=empty_payload)
