"""Single-pass vs retry-pipeline benchmark for structured decoding (F20-S1-T3).

Quantifies the round-trip (and thus token/latency) savings of a native
single-pass structured decode over the extract-validate-retry fallback, by
counting LLM round-trips and measuring wall-clock for each path against
hermetic stub providers. Marked ``@pytest.mark.benchmark``; bounds are loose to
stay non-flaky. Figures are printed for later harvesting.
"""

from __future__ import annotations

import time

import pytest
from pydantic import BaseModel

from pirn_agents.specializations.structured_output.structured_decoder import StructuredDecoder
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from tests.specializations.conftest import StubLLMProvider
from tests.specializations.structured_output.structured_stubs import (
    StubStructuredProvider,
    content_response,
)


class _UserRecord(BaseModel):
    name: str
    age: int


_VALID_JSON = '{"name": "Ada", "age": 36}'


@pytest.mark.benchmark
async def test_native_single_pass_uses_fewer_round_trips() -> None:
    decoder = StructuredDecoder(model_class=_UserRecord)

    native = StubStructuredProvider(
        capability=StructuredOutputCapability(native_schema=True),
        structured_response=content_response(_VALID_JSON),
    )
    start = time.perf_counter()
    await decoder.decode(prompt="extract a user", llm=native)
    native_seconds = time.perf_counter() - start
    native_round_trips = len(native.structured_calls) + len(native.chat_calls)

    # Retry pipeline needs an extra correction round-trip before it validates.
    retry = StubLLMProvider(['{"name": "Ada", "age": "old"}', _VALID_JSON])
    start = time.perf_counter()
    await decoder.decode(prompt="extract a user", llm=retry)
    retry_seconds = time.perf_counter() - start
    retry_round_trips = len(retry.calls)

    print(
        f"[benchmark] structured_decode native_round_trips={native_round_trips} "
        f"retry_round_trips={retry_round_trips} "
        f"native={native_seconds * 1e3:.3f}ms retry={retry_seconds * 1e3:.3f}ms"
    )

    assert native_round_trips == 1
    assert retry_round_trips >= 2
    assert native_round_trips < retry_round_trips


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_native_single_pass_uses_fewer_round_trips())
