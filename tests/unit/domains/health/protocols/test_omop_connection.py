"""Unit tests for :class:`OMOPConnection` interface."""

from __future__ import annotations

import pytest

from pirn.domains.health.protocols.omop_connection import OMOPConnection


@pytest.mark.asyncio
class TestOMOPConnectionInterface:
    async def test_query_concept_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="query_concept"):
            await OMOPConnection().query_concept(1)

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await OMOPConnection().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyOMOP(OMOPConnection):
            pass

        with pytest.raises(NotImplementedError, match="MyOMOP"):
            await MyOMOP().query_concept(1)


class TestPoolProperty:
    def test_default_pool_is_none(self) -> None:
        assert OMOPConnection().pool is None
