# Knot Design Rules Audit Report

**Scan Date:** 2026-05-06  
**Method:** Automated AST scan, all rules R1-R11 + Security

## Legend

| Column | Rule | Details |
|--------|------|---------|
| R1 | `__init__` body is ONLY `super().__init__(...)` | No validation, assignments, or logic |
| R2 | Every `__init__` param (except `_config`, `**kwargs`) appears by same name in `process()` | Ensures direct testability |
| R3 | No `raise` statements in `__init__` | All validation deferred to `process()` |
| R4 | No `self._x` assignments storing inputs | Inputs arrive fresh in `process()` |
| R5 | No `@property` exposing stored inputs or derived strings | Computed values via private helpers only |
| R6 | Opaque resources use a dedicated vending Knot, not passed directly | Live connections/sessions cannot travel the graph |
| R7 | `__init__` params use Knot types or `Knot \| scalar` — NOT plain scalars | Ensures graph wiring and lineage |
| R8 | If inherits `SubTapestry`: `process()` calls `self._run_inner()` | N/A for plain `Knot`/`Source`/`Sink` |
| R9 | Quality assessment Knots returning `QualityReport` use `*Check` suffix, not `*Gate` | N/A if not a quality assessment Knot |
| R10-Algo | Module docstring contains `Algorithm:` section | Step-by-step description |
| R10-Math | Module docstring contains `Math:` section | Always required — N/A confirmed only after reading `process()` |
| R10-Refs | Module docstring contains `References:` section | N/A if entirely pirn-native |
| Sec | Any `hashlib.md5()` call includes `usedforsecurity=False` | N/A if no md5 usage |
| Step11 | Tests call `process()` directly with plain values under `tests/unit/` | Not just via Tapestry.run() |
| Step12 | All applicable rules pass AND Step11 passes | Ready for ruff/pyright/pytest |

**Cell values:** `[x]` = compliant · `[ ]` = violation · `N/A` = rule does not apply

---

## Audit Table

### Group 1 — knots/database_connection_pool_knot.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/connectors/knots/database_connection_pool_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 2 — knots/database_execute_sink.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/connectors/knots/database_execute_sink.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 3 — knots/database_query_source.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/connectors/knots/database_query_source.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 4 — knots/message_broker_knot.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/connectors/knots/message_broker_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 5 — knots/message_broker_publish_sink.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/connectors/knots/message_broker_publish_sink.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 6 — knots/object_store_knot.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/connectors/knots/object_store_knot.py` | [x] | [x] | [x] | [x] | [x] | N/A | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 7 — knots/object_store_list_source.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/connectors/knots/object_store_list_source.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 8 — knots/object_store_read_source.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/connectors/knots/object_store_read_source.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

### Group 9 — knots/object_store_write_sink.py

| File | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10-Algo | R10-Math | R10-Refs | Sec | Step11 | Step12 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| `pirn/domains/connectors/knots/object_store_write_sink.py` | [x] | [x] | [x] | [x] | [x] | [x] | [x] | N/A | N/A | [x] | N/A | [x] | N/A | [x] | [x] |

