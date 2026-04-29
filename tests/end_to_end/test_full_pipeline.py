"""End-to-end pipeline combining multiple node types."""

from __future__ import annotations

from pirn import (
    Aggregator,
    Gate,
    KnotConfig,
    Map,
    Parameter,
    Reduce,
    RunRequest,
    Tapestry,
    knot,
)


async def test_realistic_data_pipeline():
    """A representative pipeline:
    1. Source: a list of records as Parameter.
    2. Map: enrich each record.
    3. Reduce: sum a field across all records.
    4. Aggregator: combine reduced summary with metadata.
    5. Gate: only emit if total above a threshold.
    6. Branch: route by a flag.
    """

    @knot
    async def enrich(record: dict) -> dict:
        return {**record, "score": record["base"] * 10}

    @knot
    async def get_total(items: list[dict]) -> int:
        return sum(it["score"] for it in items)

    @knot
    async def get_count(items: list[dict]) -> int:
        return len(items)

    with Tapestry() as t:
        records = Parameter(
            "records",
            list[dict],
            default=[
                {"base": 1, "tag": "x"},
                {"base": 2, "tag": "y"},
                {"base": 3, "tag": "x"},
            ],
        )
        threshold = Parameter("threshold", int, default=10)

        enriched = Map(
            over=records,
            each=enrich,
            bind="record",
            _config=KnotConfig(id="enriched"),
        )

        total_score = Reduce(
            of=enriched,
            combine=lambda items: sum(it["score"] for it in items),
            _config=KnotConfig(id="total_score"),
        )

        count = get_count(items=enriched, _config=KnotConfig(id="count"))

        summary = Aggregator(
            combine=lambda total, count: {"total": total, "count": count},
            total=total_score,
            count=count,
            _config=KnotConfig(id="summary"),
        )

        gate = Gate(
            input=total_score,
            predicate=lambda v: v > 10,
            _config=KnotConfig(id="big_enough"),
        )

        @knot
        async def announce(s: dict) -> str:
            return f"Found {s['count']} records, total {s['total']}"

        # Wire announce after gate (will run only if gate opens) AND summary
        @knot
        async def gated_summary(g: int, s: dict) -> dict:
            return {**s, "gated_total": g}

        gated_summary(g=gate, s=summary, _config=KnotConfig(id="final"))

    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["enriched"] == [
        {"base": 1, "tag": "x", "score": 10},
        {"base": 2, "tag": "y", "score": 20},
        {"base": 3, "tag": "x", "score": 30},
    ]
    assert result.outputs["total_score"] == 60
    assert result.outputs["count"] == 3
    assert result.outputs["summary"] == {"total": 60, "count": 3}
    assert result.outputs["big_enough"] == 60  # gate open
    assert result.outputs["final"] == {"total": 60, "count": 3, "gated_total": 60}


async def test_pipeline_with_gate_closed_skips_downstream():
    """Same pipeline but with all-zero records → gate closes."""

    @knot
    async def enrich(record: dict) -> dict:
        return {**record, "score": record["base"] * 10}

    with Tapestry() as t:
        records = Parameter(
            "records",
            list[dict],
            default=[{"base": 0, "tag": "x"}],
        )

        enriched = Map(
            over=records,
            each=enrich,
            bind="record",
            _config=KnotConfig(id="enriched"),
        )
        total = Reduce(
            of=enriched,
            combine=lambda items: sum(it["score"] for it in items),
            _config=KnotConfig(id="total"),
        )
        gate = Gate(
            input=total,
            predicate=lambda v: v > 100,
            _config=KnotConfig(id="big"),
        )

        @knot
        async def consume(v: int) -> str:
            return f"got {v}"

        consume(v=gate, _config=KnotConfig(id="c"))

    result = await t.run(RunRequest())
    assert result.outputs["total"] == 0
    assert "big" in result.skipped
    assert "c" in result.skipped
    assert "c" not in result.outputs
