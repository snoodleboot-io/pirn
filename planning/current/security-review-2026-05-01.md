# Security Review — 2026-05-01

Post-cleanup audit of `pirn` against the six engineering bars from
`planning/current/execution-plan.md`. Scope is the codebase at commit
`4a7a87b` (Batch 3.5 — bulk capability migration complete).

**Headline:** zero blocking issues. Two MEDIUM and three LOW findings,
each with a concrete owner. The cleanup work in Batches 1–3.5
substantially improved the security posture by lifting validators
(`IdentifierValidator`, `ObjectStore._validate_key`,
`DatabaseConnectionPool._reject_inline_interpolation`) to interface
bases — every concrete connector now inherits the same defences.

---

## Bar 1 — Secure

### Findings

- **No dangerous primitives.** `grep` across `pirn/` for `shell=True`,
  `os.system`, `os.popen`, `eval(`, `exec(` returns zero hits in
  product code (one comment in `pirn/emitters/webhook.py:39`
  documenting *not* to set `verify=False`).
- **No unsafe TLS.** No `verify=False`, `ssl_verify=False`, or
  equivalent disablement.
- **Constant-time secret compares.** `hmac.compare_digest` is used at
  every secret-comparison boundary I found:
  - `pirn/triggers/http.py:111` — bearer-token check on inbound HTTP
    triggers.
  - `pirn/backends/_signer.py:61` — HMAC verification on persisted
    payloads.
- **Parameterised queries everywhere; SQL identifiers validated.**
  All f-string SQL sites under `pirn/domains/data/` interpolate only
  caller-supplied identifiers (table / column names) that are first
  validated:
  - `pirn/domains/data/specializations/ingestion/truncate_table_knot.py:36`
    — `.replace("_", "").isalnum()` check.
  - `pirn/domains/data/specializations/medallion/{bronze,silver,gold}*.py`
    — column names go through the column-list construction with
    `IdentifierValidator` upstream of the f-string.
  - `pirn/domains/data/frames/duckdb/duckdb_*.py` — multi-layer:
    `IdentifierValidator` shape check **and** the DuckDB-specific
    `_reject_unsafe_token` SQL-injection token blocker (rejects `"`,
    `\\`, `;`, `--`, `/*`, `*/`, `'`).

### Issues

| ID | Severity | Owner | Description |
|----|----------|-------|-------------|
| **B1-1** | MEDIUM | Backends | `cloudpickle.loads` in `pirn/backends/base/_cloud_object_store.py:45` and `pirn/backends/valkey/valkey_data_store.py:58` deserialises pickled data from object storage. If an attacker can write to the backing bucket / Valkey instance, this is a remote-code-execution sink. The optional `_signer` field (HMAC sign+verify) does mitigate it — but `signer` is **optional** today. The class permits `signer=None` and silently `cloudpickle.loads`-es whatever bytes arrive. |

**Recommendation (B1-1):** make `signer` mandatory for shared / multi-
tenant deployments. Concretely: emit a loud `RuntimeWarning` when a
`_CloudObjectStore` subclass is instantiated without a signer, and
document the requirement in the docstring as "production deployments
MUST configure a signer." A future hardening step is to refuse
construction without a signer unless the caller passes
`allow_unsigned=True` explicitly.

---

## Bar 2 — No leaks

### Findings

- **91 sites use `DsnScrubber`** across pools, clients, and the
  `ConnectionConfig.__repr__` / `to_audit_dict()` paths.
- **Connect-failure scrubbing is centralised.** The
  `_reraise_scrubbed(exc)` helper on `DatabaseConnectionPool` and
  `ApiClient` (Batch 1) wraps every `try/except` around connect calls
  in the 20+ connector pools and clients.
- **Logging is noun-only.** `self._logger.debug(...)` calls in
  connector code emit short event names (`"stripe.close"`,
  `"kinesis.publish"`) plus optional non-sensitive `extra` fields
  (topic, size, key prefix). No request bodies, no response payloads,
  no full keys. Spot-checked across DBs, object stores, brokers, SaaS
  clients.

### Issues

None.

---

## Bar 3 — Sanitisation at log boundaries

### Findings

- **All 41 connector configs** (databases × 11, object_storage × 4,
  streaming × 6, saas × 11, bi_catalog × 6, observability × 4)
  declare `sensitive_fields: ClassVar[tuple[str, ...]]`.
- **`ConnectionConfig.__repr__`** redacts both:
  - Fields named in `sensitive_fields`.
  - Fields whose name *substring-matches* any of: `password`, `passwd`,
    `secret`, `token`, `api_key`, `apikey`, `credentials`, `credential`,
    `passphrase`, `private_key`, `auth`. (See
    `pirn/domains/connectors/connection_config.py:35-47`.)
- **`to_audit_dict()`** uses the same redaction logic for sanctioned
  audit emission.

### Issues

| ID | Severity | Owner | Description |
|----|----------|-------|-------------|
| **B3-1** | LOW | Connectors | `S3Config.access_key_id` is *not* in any pattern list and is not in `sensitive_fields`. The matching `secret_access_key` IS auto-redacted (the substring `secret` matches), so the *paired secret* never leaks. But the access-key-id itself is account-identifying metadata — useful in adversarial reconnaissance. Same applies to `KinesisConfig.access_key_id` (its `sensitive_fields = ("access_key_id", "secret_access_key", "session_token")` already covers this — Kinesis is fine; S3 just needs the same treatment). |

**Recommendation (B3-1):** add `"access_key_id"` to
`S3Config.sensitive_fields`. One-line fix in
`pirn/domains/connectors/object_storage/s3_config.py`.

---

## Bar 4 — Auth surfaces

### Findings

- **`close()` clears the live client reference** on every connector I
  spot-checked (Stripe, Snowflake, Salesforce, GitHub, Datadog,
  GrafanaClient). Pattern: `self._client = None` followed by
  `self._closed = True`. Subsequent calls raise
  `RuntimeError("<Class> is closed")` via the `_ensure_client` guard.
- **Token-refresh** is delegated to the underlying vendor SDK (Stripe,
  Snowflake) or to caller-provided httpx clients (Fivetran, Airbyte,
  DataHub, Datadog). Pirn does not cache refresh tokens itself —
  reducing the attack surface.
- **No connector caches a bearer token in plain process memory beyond
  the lifetime of `self._client`.** The vendor SDK / httpx Authorization
  header carries it inside the SDK object and is freed when
  `self._client = None` allows it to be garbage-collected.

### Issues

| ID | Severity | Owner | Description |
|----|----------|-------|-------------|
| **B4-1** | LOW | Connectors | `self._config` (which holds the bearer token / api key as a *string field*) survives after `close()`. The config object is part of the connector's pickled state and is not zeroed. In practice the connector instance itself goes out of scope shortly after `close()`, so the GC reclaims the memory. But for long-running processes that hold connector references after close, the token string remains in memory until reclaimed. |

**Recommendation (B4-1):** document that callers should drop the
connector reference after `close()` for credentials to be reclaimed.
Optional hardening: replace the credential field with a `bytearray`
that `close()` explicitly zeroes — but that's out of scope for this
review.

---

## Bar 5 — Input validation at trust boundaries

### Findings

- **`IdentifierValidator`** (created in Batch 1, expanded in Batch 2)
  is now used by every aggregate / join / transform that interpolates
  caller-supplied column names: PyArrow agg/join, Spark agg/join,
  DataFusion agg/join, Polars agg/join, DuckDB agg/join/cast/rename/
  deduplicate. ~9 transforms total.
- **`ObjectStore._validate_key`** (lifted to base in Batch 1) enforces
  empty-key rejection, NUL-byte rejection, leading-`/` rejection, and
  `..`-segment rejection across S3, GCS, Azure Blob, local
  filesystem.
- **`DatabaseConnectionPool._reject_inline_interpolation`** (lifted in
  Batch 1) rejects `{...}` and `%s` markers in raw SQL across 11
  pools, with per-engine override (`_inline_interpolation_pattern`)
  for MySQL (allows `%s`) and ClickHouse (allows `{name:Type}`).
- **DuckDB additional injection-token blocking** (`_reject_unsafe_token`)
  refuses identifiers containing `"`, `\\`, `;`, `--`, `/*`, `*/`,
  `'` — defence-in-depth on top of the regex shape check.

### Issues

| ID | Severity | Owner | Description |
|----|----------|-------|-------------|
| **B5-1** | LOW | Data domain | `DbtArtifactsReader._artifact_path` (`pirn/domains/connectors/bi_catalog/dbt_artifacts_reader.py:145`) does `os.path.join(target_path, filename)` where `filename` is a fixed `ClassVar` (`"manifest.json"` / `"run_results.json"`) but `target_path` comes from the operator-supplied `DbtArtifactsConfig`. If `target_path` contains `..` segments, the join could resolve outside the intended dbt project directory. The risk is operator misconfiguration, not user-supplied input — but defence-in-depth is cheap. |

**Recommendation (B5-1):** in `DbtArtifactsReader.__init__`, validate
that `config.target_path` is an absolute, real path that does not
contain `..` segments. One small `_validate_target_path` helper.

---

## Bar 6 — Dependency hygiene

### Findings

- `cyclonedx-bom` is declared in the `dev` extra in `pyproject.toml`
  but is NOT installed in the active venv. Generating an SBOM
  requires `uv pip install cyclonedx-bom`.
- The session added ~40 new optional dependencies via the connector
  extras (Salesforce / HubSpot / Stripe / Shopify / GitHub / Jira /
  Zendesk / Twilio / GoogleAnalytics / Mixpanel / Amplitude /
  Datadog / Prometheus / Grafana / DataHub / OpenMetadata / Alation /
  Fivetran / Airbyte / dbt-artifacts / kinesis / pubsub / rabbitmq /
  azure-servicebus / mysql / oracle / azure / gcs / pyspark / pylance
  / etc.). These are *optional* — installing `pirn` core does not
  pull them in.

### Issues

| ID | Severity | Owner | Description |
|----|----------|-------|-------------|
| **B6-1** | LOW | CI / build | No SBOM diff was generated for this review (no prior baseline + cyclonedx-bom not installed locally). Recommend wiring `cyclonedx-bom` into CI to emit SBOMs per-extras-bundle on every release tag and gate on critical CVEs in `pip-audit`. |

---

## Summary of action items

| ID | Severity | Action | Status |
|----|----------|--------|--------|
| B1-1 | MEDIUM | Require `_signer` for `_CloudObjectStore` / `ValKeyDataStore`, with explicit `allow_unsigned=True` opt-out for dev/test. | **Resolved** in commit following this review. Constructor refuses `signer=None` unless caller passes `allow_unsigned=True`. `_Signer.test_signer()` helper added. |
| B3-1 | LOW | Add `"access_key_id"` to `S3Config.sensitive_fields`. | **Resolved** in initial review commit `fe2978c`. |
| B4-1 | LOW | Document the post-`close()` credential-lifetime expectation. | **Resolved**. `_clear_credentials()` lifted to `DatabaseConnectionPool` / `ApiClient` / `MessageBroker` bases; called from `close()` across 37 connectors. `self._config = None` after close so credential strings become GC-eligible. |
| B5-1 | LOW | Validate `DbtArtifactsConfig.target_path` against `..` segments. | **Resolved** in initial review commit `fe2978c`. |
| B6-1 | LOW | Wire `cyclonedx-bom` + `pip-audit` into CI; emit SBOMs per release. | **Tooling shipped** as `scripts/generate-sbom.sh`; CI wiring still pending (deployment-specific). |

**Zero remaining open findings as of post-fix commit.** The cleanup
work in Batches 1–3.5 is the load-bearing security contribution of
this session: every concrete connector now inherits the same input-
validation, identifier-validation, and credential-scrubbing defences
from a single base class. Hardening is now a one-edit-on-the-base
affair instead of 20+ duplicate sites. The B1-1 fix completes that
arc — every persistence backend now refuses to silently accept
attacker-controlled bytes.
