"""Tests verifying that IDataTransport is wired through Tapestry → Engine."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.transport.inline_transport import InlineTransport
from pirn.tapestry import Tapestry


@knot
async def double(x: int, **_) -> int:
    return x * 2


@knot
async def add(a: int, b: int, **_) -> int:
    return a + b


class TestTransportWiring(unittest.IsolatedAsyncioTestCase):
    async def test_default_transport_is_inline(self) -> None:
        t = Tapestry()
        assert isinstance(t.transport, InlineTransport)

    async def test_custom_transport_stored(self) -> None:
        custom = InlineTransport(warn_above_bytes=1)
        t = Tapestry(transport=custom)
        assert t.transport is custom

    async def test_pipeline_runs_correctly_with_inline_transport(self) -> None:
        with Tapestry() as t:
            p = Parameter("x", int)
            d = double(x=p, _config=KnotConfig(id="d"))
            a = add(a=p, b=d, _config=KnotConfig(id="answer"))

        result = await t.run(RunRequest(parameters={"x": 5}))
        assert result.succeeded
        assert result.outputs["d"] == 10
        assert result.outputs["answer"] == 15

    async def test_pipeline_runs_correctly_with_filesystem_transport(self) -> None:
        import tempfile
        from pathlib import Path

        from pirn.core.transport.filesystem_transport import FilesystemTransport

        with tempfile.TemporaryDirectory() as tmp:
            fs = FilesystemTransport(base_dir=Path(tmp), sweep_on_startup=False)
            with Tapestry(transport=fs) as t:
                p = Parameter("x", int)
                d = double(x=p, _config=KnotConfig(id="d"))

            result = await t.run(RunRequest(parameters={"x": 7}))
            assert result.succeeded
            assert result.outputs["d"] == 14

    async def test_transport_begin_and_end_run_called(self) -> None:
        mock_transport = InlineTransport()
        mock_transport.begin_run = AsyncMock(wraps=mock_transport.begin_run)
        mock_transport.end_run = AsyncMock(wraps=mock_transport.end_run)

        with Tapestry(transport=mock_transport) as t:
            p = Parameter("x", int)
            double(x=p, _config=KnotConfig(id="d"))

        await t.run(RunRequest(parameters={"x": 3}))
        mock_transport.begin_run.assert_called_once()
        mock_transport.end_run.assert_called_once()

    async def test_transport_write_called_per_successful_knot(self) -> None:
        mock_transport = InlineTransport()
        mock_transport.write = AsyncMock(wraps=mock_transport.write)

        with Tapestry(transport=mock_transport) as t:
            p = Parameter("x", int)
            d = double(x=p, _config=KnotConfig(id="d"))
            add(a=p, b=d, _config=KnotConfig(id="answer"))

        await t.run(RunRequest(parameters={"x": 4}))
        assert mock_transport.write.call_count == 3

    async def test_end_run_called_with_success_true_on_clean_run(self) -> None:
        mock_transport = InlineTransport()
        mock_transport.end_run = AsyncMock(wraps=mock_transport.end_run)

        with Tapestry(transport=mock_transport) as t:
            p = Parameter("x", int)
            double(x=p, _config=KnotConfig(id="d"))

        await t.run(RunRequest(parameters={"x": 1}))
        _, kwargs = mock_transport.end_run.call_args
        assert kwargs["success"] is True
