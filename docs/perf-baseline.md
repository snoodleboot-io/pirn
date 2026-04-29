# Performance baseline

Measured on: Python 3.14.3, Linux 6.17, single core, no real backends for
SQLite benchmarks.  Run benchmarks yourself with:

```bash
uv run python -m pytest tests/perf/ --benchmark-columns=mean,stddev,rounds
```

## Wave-loop throughput (chain tapestry, no real work per knot)

| knots | mean    | notes |
|-------|---------|-------|
| 10    | 631 µs  | ~15 800 runs/sec |
| 100   | 5.5 ms  | ~182 runs/sec |
| 500   | 47 ms   | ~21 runs/sec |

Throughput is roughly linear in knot count — dominated by asyncio task
scheduling overhead (~6 µs/knot), not pirn framework code.

## Content hashing

| payload     | mean     | notes |
|-------------|----------|-------|
| small dict  | 7.7 µs   | typical knot output |
| 10 000-item list | 891 µs | sorted hash of elements |
| 1 MB bytes  | 7.1 ms   | ~140 MB/s |
| 10 MB bytes | 68 ms    | ~147 MB/s |
| 100 MB bytes | 759 ms  | ~132 MB/s |

Hashing throughput is ~140 MB/s.  For knots producing large numpy arrays
or dataframes, consider hashing a summary (shape + dtype + sample) rather
than the full payload to avoid the per-run hashing cost.

## Status-event fanout

| emitters | sync mean | async mean |
|----------|-----------|------------|
| 10       | 298 µs    | 290 µs     |
| 100      | 1 715 µs  | 1 742 µs   |

Fanout scales linearly (~17 µs/emitter).  100 emitters adds ~1.7 ms to
every run.  Async and sync emitters have similar overhead — asyncio task
creation is cheap.

## SQLite lineage write rate

| runs | mean    | rate |
|------|---------|------|
| 10   | 2.4 ms  | ~4 200 runs/sec |
| 100  | 20 ms   | ~4 900 runs/sec |
| 1 000 | 196 ms | ~5 100 runs/sec |

SQLite in WAL mode sustains ~5 000 lineage writes/sec.  Each write is a
`BEGIN` / multiple `INSERT` / `COMMIT` cycle; see P4.2 for batching.

## Postgres lineage write rate

Run with `--real` and `PIRN_TEST_POSTGRES_URL` set to get Postgres numbers.
Expected: 500–2 000 runs/sec depending on pool size and network latency.

## Known bottlenecks

1. **Hashing large outputs** — if knots produce blobs >1 MB, hashing cost
   becomes significant.  Mitigation: hash a fingerprint instead.
2. **SQLite per-run commit overhead** — each `record_run` call commits a
   transaction.  Batching (P4.2) is expected to yield 5–10× improvement.
3. **Status fanout at >100 emitters** — linear cost; use sparingly.
