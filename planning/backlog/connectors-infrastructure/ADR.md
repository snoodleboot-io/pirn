# ADR: Connectors Infrastructure

**Status:** TBD — to be written when sprint starts
**Initiative:** connectors-infrastructure
**Depends on:** domain-knot-libraries ADR (assembler/disassembler, Payload[M,D], single-package)

---

## Context

Connectors require credential handling, connection pooling, batch sizing, and backpressure — all of which have architectural implications that cut across every connector knot. The domain-knot-libraries initiative deferred these questions and shipped thin config + pool classes. Before implementing the missing 48 knot classes, these questions must be answered consistently.

The existing generic knots (`DatabaseQuerySource`, `DatabaseExecuteSink`, `ObjectStoreReadSource`, `MessageBrokerPublishSink`) provide a working pattern for simple read/write. The decisions below extend that pattern to more complex operations without breaking existing knots.

---

## Open Architectural Questions

These must be resolved before implementation begins.

**1. SecretStr vs env-var injection for credential handling**

Connector configs currently hold credentials as plain strings. The options are:
- `SecretStr` (pydantic) — masks secrets in repr/logs; provides a single consistent field type; but requires pydantic in the connector extras.
- `CredentialProvider` abstraction — a protocol or interface that the config consults at connect time, decoupling the credential source (env, vault, AWS Secrets Manager) from the config dataclass; adds indirection but enables secret rotation without reconnection.
- Environment variable convention — configs read from env at construction; simple but difficult to test and inflexible in multi-tenant deployments.

The decision must specify which approach is standard for new connector configs and whether existing configs are migrated.

**2. Source owns connection lifecycle vs external pool**

Currently, pool classes (`PostgresPool`, `KafkaBroker`, etc.) are separate from knots. The question is the contract: does the `DatabaseQuerySource` knot receive an already-initialised pool via constructor injection, or does it instantiate one from config? Constructor injection allows sharing a pool across knots in a tapestry (important for connection limits), but requires the tapestry author to wire the pool. Self-instantiation is simpler to use but creates one pool per knot, which is wrong for most databases.

**3. DataBatch size negotiation protocol**

Bulk and streaming knots need a way to express preferred batch sizes. Connectors like BigQuery or Kafka have optimal batch sizes that differ from pirn's internal `DataBatch` sizing. The options are: a `batch_size` config field per knot (simple, no framework changes), a `BatchSizeHint` that the framework passes at init time (more flexible, requires framework change), or leaving batch sizing entirely to the source and letting downstream knots handle variable batch sizes. The decision affects whether bulk-load knots can adapt to memory pressure.

**4. Tiered engine compatibility guarantee**

Connector knots emit `DataBatch` (Tier 1). When a downstream knot expects a Polars `DataFrame` (Tier 2), a bridge knot is required. The question is whether connector knots should optionally emit native Tier 2 types directly (by accepting a `target_tier` config) or always emit `DataBatch` and require explicit bridge knots. The always-DataBatch approach is simpler and consistent with the tiered architecture design; the optional-native approach avoids the bridge knot hop for the common case.

---

## Decision

TBD — document decisions here when the sprint is planned.

---

## Consequences

TBD.
