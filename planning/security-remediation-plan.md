# Security Remediation Plan

**Source:** `planning/security-analysis.md`  
**Created:** 2026-04-29  
**Branch:** feat/security-compliance-docs

---

## Status Key

| Status | Meaning |
|--------|---------|
| ✅ Done | Resolved in this session |
| ⚠️ Partial | Partially resolved; remaining work tracked below |
| 🔲 Open | Not yet started |

---

## Finding Status Summary

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| C-1 | CRITICAL | Insecure deserialization — pickle over untrusted stores | ✅ Done |
| H-2 | HIGH | Arbitrary code execution via YAML loader dynamic imports | ✅ Done |
| H-3 | HIGH | Unauthenticated HTTP trigger | ✅ Done |
| M-4 | MEDIUM | Credential exposure — DSN in tracebacks | ✅ Done |
| M-5 | MEDIUM | Emitter failures silently discarded | ✅ Done |
| M-6 | MEDIUM | No TLS config for WebhookEmitter | ✅ Done |
| M-7 | MEDIUM | Full tracebacks stored persistently | ✅ Done |
| L-8 | LOW | Insufficient run_id entropy | ✅ Done |
| L-9 | LOW | knot_id not validated for special characters | ✅ Done |
| L-10 | LOW | WebhookEmitter SSRF potential | ✅ Done |
| I-11 | INFO | No SECURITY.md | ✅ Done |
| I-12 | INFO | No SBOM | ✅ Done |
| I-13 | INFO | aiokafka as core dependency | ✅ Done |
| I-14 | INFO | Pickle protocol version unspecified | ✅ Done |

---

## Already Resolved (this session)

### ✅ L-8 — run_id entropy
`uuid.uuid4().hex[:12]` → `uuid.uuid4().hex`. Full 128-bit entropy. No further work needed.

### ✅ I-11 — SECURITY.md
`SECURITY.md` created at repo root with responsible disclosure policy and scope. No further work needed.

### ✅ I-13 — aiokafka optional
Moved from base `dependencies` to `[kafka]` optional extra in `pyproject.toml`. No further work needed.

---

## Partially Resolved

### ⚠️ H-2 — YAML loader dynamic imports
**Done:** `warnings.warn()` fires when `allow_callable_refs=True`.  
**Remaining:**
- Add `allowed_modules: list[str]` parameter to `load_pipeline()` — reject any callable ref whose module path does not start with an allowlisted prefix
- Update `docs/architecture.md` YAML section to document the allowlist parameter
- Add tests for the allowlist enforcement

### ⚠️ M-5 — Emitter failures
**Done:** bare `except Exception: pass` replaced with `_log.warning(...)` for `on_lineage` and `on_run_result`.  
**Remaining:**
- Add a configurable `EmitterErrorPolicy` enum: `WARN` (default), `IGNORE`, `RAISE`
- Expose on `Tapestry(emitter_error_policy=...)` and `tapestry.run(emitter_error_policy=...)`
- Add `pirn.emitter.failures` counter using Python's `statistics` or a simple in-process counter exposed via the emitter protocol — or document how to wire it to OTel metrics

---

## Open Work (ordered by priority)

---

### 1. C-1 — Insecure deserialization (CRITICAL)

**Goal:** Eliminate RCE via pickle in `S3DataStore`, `ValKeyDataStore`, and `LocalDiskDataStore`.

**Approach:** Two-track.

**Track A — HMAC signing (near-term, non-breaking)**  
Add optional HMAC integrity verification to all three backends. When a `signing_key` is supplied, every `put()` signs the payload and every `get()` verifies before deserializing. A tampered or unsigned payload raises `ValueError` and never reaches `pickle.loads()`.

- `pirn/backends/s3.py` — add `signing_key: bytes | None = None` to `S3DataStore.__init__()`; implement `_sign(payload)` / `_verify_and_strip(payload)` helpers using `hmac.new(..., hashlib.sha256)`
- `pirn/backends/valkey.py` — same on `ValKeyDataStore`
- `pirn/backends/disk.py` — same on `LocalDiskDataStore` (which already has `_serialize`/`_deserialize` hooks — layer signing there)
- `pirn/backends/__init__.py` — export a `DataStoreSigningKey` helper that reads a key from an env var
- Add tests: unsigned payload rejected when key configured; signed payload accepted; tampered payload rejected

**Track B — Serializer hooks (medium-term, recommended for new deployments)**  
Promote the `_serialize`/`_deserialize` override pattern from `LocalDiskDataStore` to all three backends. Document a `MsgspecDataStore` mixin in `docs/choosing-backends.md` that operators drop in for JSON-safe serialization.

**Support doc needed:** Add a "Serialization and data integrity" section to `docs/choosing-backends.md` covering:
- Why pickle is used by default
- When HMAC signing is sufficient
- When to replace pickle entirely (cross-language, untrusted store, compliance requirements)
- Example `MsgspecDataStore` subclass

---

### 2. H-3 — Unauthenticated HTTP trigger (HIGH)

**Goal:** Give `WebhookTrigger` a built-in, low-friction authentication option so operators are not left to wire auth themselves.

**Approach:**

- Add `auth_token: str | None = None` parameter to `WebhookTrigger.__init__()`. When set, the Starlette handler checks `Authorization: Bearer <token>` and returns HTTP 401 if absent or wrong. Token comparison uses `hmac.compare_digest` (constant-time).
- Add `rate_limit_rpm: int | None = None` parameter. Implement a simple sliding-window counter per source IP using a `collections.deque`. Return HTTP 429 when exceeded.
- Update module docstring with a working auth example.
- Add a new doc: `docs/webhook-trigger-auth.md` — covers bearer token setup, env var pattern, Starlette middleware for mTLS, and reverse proxy configuration (nginx snippet, AWS API Gateway note).
- Add tests: unauthenticated request rejected (401), wrong token rejected (401), correct token accepted, rate limit enforced (429).

---

### 3. M-4 — DSN credential exposure (MEDIUM)

**Goal:** Prevent Postgres passwords from appearing in `ExceptionRecord.traceback_text`.

**Approach:**

- In `pirn/backends/postgres.py` `_LazyPool.get()`, wrap `asyncpg.create_pool(self._dsn)` in a try/except that catches `Exception` and re-raises with a sanitized message:
  ```python
  except Exception as exc:
      safe_msg = re.sub(r'://[^@]+@', '://<redacted>@', str(exc))
      raise type(exc)(safe_msg) from None
  ```
- Remove `self._dsn` as a persistent instance attribute — store it only as a local variable inside `get()`, retrieved from a callable or closure so it is not reachable from tracebacks at the instance level.
- Add tests: connection failure with a DSN containing credentials produces an exception whose `str()` does not contain the password.

---

### 4. M-7 — Full tracebacks stored persistently (MEDIUM)

**Goal:** Prevent secrets in local variables from being persisted in `ExceptionRecord.traceback_text`.

**Approach:**

- Add a `traceback_filter: Callable[[str], str] | None = None` parameter to `ExceptionManager.__init__()`.
- When set, apply it to `traceback_text` before creating the `ExceptionRecord`.
- Ship a built-in `pirn.managers.exceptions.redact_common_secrets` filter function that applies regex scrubbing for common patterns (DSNs, `password=`, `token=`, `api_key=`, `Authorization: Bearer`).
- Expose `ExceptionManager` configuration through `Tapestry` constructor: `Tapestry(traceback_filter=redact_common_secrets)`.
- Add `docs/exception-handling.md` covering: what gets stored, how to configure the filter, the built-in filter patterns, and a guide on writing custom filters.
- Add tests: filter applied before storage; default (no filter) stores verbatim; built-in filter redacts a DSN-containing traceback.

---

### 5. M-5 (remaining) — EmitterErrorPolicy (MEDIUM)

**Goal:** Give operators control over emitter failure behavior.

**Approach:**

- Add `EmitterErrorPolicy(StrEnum)` to `pirn/emitters/base.py`: `WARN` (default), `IGNORE`, `RAISE`.
- Thread it through `Engine._execute_loop()` — replace the current `_log.warning(...)` with a dispatch on the policy.
- Expose on `Tapestry(emitter_error_policy=EmitterErrorPolicy.WARN)` and `tapestry.run(emitter_error_policy=...)`.
- Update `docs/observability.md` with a section on emitter reliability and policy options.
- Add tests for each policy variant.

---

### 6. M-6 — WebhookEmitter TLS configuration (MEDIUM)

**Goal:** Give operators a safe, documented path to custom CA bundles without disabling TLS verification.

**Approach:**

- Add `verify: bool | str = True` and `ssl_context: ssl.SSLContext | None = None` to `WebhookEmitter.__init__()`. Pass both to `httpx.AsyncClient`.
- Add a docstring note: "`verify=False` must never be used in production."
- Update `docs/observability.md` with a "WebhookEmitter TLS" section covering custom CA setup and client certificates.
- Add tests: custom `ssl_context` is passed to the client; `verify=True` is the default.

---

### 7. H-2 (remaining) — YAML loader allowlist (HIGH)

**Goal:** Let operators restrict which Python modules `allow_callable_refs` can import.

**Approach:**

- Add `allowed_module_prefixes: list[str] | None = None` to `load_pipeline()`.
- In `_resolve_callable()`, when `allow_imports=True` and `allowed_module_prefixes` is set, check that `module_path` starts with at least one prefix before importing. Raise `ValueError` with a clear message if not.
- Update `PipelineSpec` to optionally carry an `allowed_module_prefixes` field so it can be declared in the YAML itself (defence in depth — the YAML declares its own import scope).
- Update `docs/architecture.md` YAML loader section.
- Add tests: disallowed module path raises; allowed module path imports; no prefixes + allow_imports works as before.

---

### 8. L-9 — knot_id validation (LOW)

**Goal:** Reject knot_ids that contain characters which could cause log injection, path confusion, or display issues.

**Approach:**

- Add a Pydantic `field_validator` to `KnotConfig.id`:
  ```python
  KNOT_ID_RE = re.compile(r'^[a-zA-Z0-9_\-\.:]{1,256}$')
  ```
  The character set allows `:` (used by the `param:name` convention) and `.` (common in hierarchical ids like `etl.load.users`). Null bytes, path separators, whitespace, and control characters are rejected.
- Add tests: valid ids pass; null byte rejected; path separator rejected; empty string rejected (already enforced by `min_length=1`).
- Note in `docs/architecture.md` Core Concepts section.

---

### 9. L-10 — WebhookEmitter SSRF (LOW)

**Goal:** Document that URLs must be static and add a construction-time guard.

**Approach:**

- Add a `_validate_url(url: str)` helper called in `WebhookEmitter.__init__()` that:
  1. Parses the URL with `urllib.parse.urlparse`
  2. Rejects non-http/https schemes
  3. Optionally rejects RFC-1918 / loopback hostnames when `block_private_ips=True` (default `False` to avoid breaking existing internal deployments, but documented as the recommended production setting)
- Update the class docstring to note that URLs must be static deployment constants.
- Update `docs/observability.md` with a "WebhookEmitter security" note.
- Add tests: non-https scheme rejected; private IP blocked when flag set.

---

### 10. I-12 — SBOM generation (INFO)

**Goal:** Generate and publish a Software Bill of Materials on every release.

**Approach:**

- Add `cyclonedx-bom` to the `[dev]` optional extra in `pyproject.toml`.
- Add a step to `.github/workflows/ci.yml` on the release job:
  ```yaml
  - name: Generate SBOM
    run: uv run cyclonedx-py environment -o sbom.json --schema-version 1.5
  - uses: actions/upload-artifact@v4
    with:
      name: sbom-${{ github.sha }}
      path: sbom.json
  ```
- Pin all GitHub Actions to SHA digests (currently using mutable `@v4`/`@v5`/`@v6` tags — supply-chain risk noted in analysis).
- Add Dependabot config (`.github/dependabot.yml`) for both `pip` and `github-actions` ecosystems.

---

### 11. I-14 — Pickle protocol version (INFO)

**Goal:** Make the pickle protocol explicit and document cross-version limitations.

**Approach:**

- Change all `pickle.dumps(value)` to `pickle.dumps(value, protocol=5)` in `s3.py`, `valkey.py`, and `disk.py`.
- Add a module-level constant `_PICKLE_PROTOCOL = 5` in each file.
- Add a note to `docs/choosing-backends.md` under each affected backend: payloads written with protocol 5 require Python 3.8+; payloads are not cross-version compatible.

---

## Support Documents Needed

| Document | Triggered by | Status |
|----------|-------------|--------|
| `docs/choosing-backends.md` — "Serialization and data integrity" section | C-1 | 🔲 |
| `docs/webhook-trigger-auth.md` | H-3 | 🔲 New file |
| `docs/observability.md` — "WebhookEmitter TLS" section | M-6 | 🔲 |
| `docs/observability.md` — "Emitter reliability and error policy" section | M-5 | 🔲 |
| `docs/observability.md` — "WebhookEmitter security" note | L-10 | 🔲 |
| `docs/exception-handling.md` | M-7 | 🔲 New file |
| `docs/architecture.md` — YAML allowlist section update | H-2 | 🔲 |
| `docs/architecture.md` — knot_id validation note | L-9 | 🔲 |
| `.github/dependabot.yml` | I-12 | 🔲 New file |

---

## Suggested Implementation Order

Group findings into three sprints by risk and interdependency:

**Sprint 1 — Critical & High (do first)**
1. C-1 Track A (HMAC signing) — highest risk, self-contained
2. H-3 (webhook auth) — high risk, self-contained
3. H-2 remaining (allowlist) — small addition to existing warning

**Sprint 2 — Medium**
4. M-4 (DSN scrubbing) — targeted, low-risk change
5. M-7 (traceback filter) — builds on M-4 patterns; new `Tapestry` param
6. M-5 remaining (EmitterErrorPolicy) — small enum + wiring
7. M-6 (WebhookEmitter TLS) — additive constructor params

**Sprint 3 — Low & Info + Support docs**
8. L-9 (knot_id validation)
9. L-10 (SSRF guard)
10. I-12 (SBOM + Dependabot + SHA-pin CI actions)
11. I-14 (explicit pickle protocol)
12. All support documentation

---

## Out of Scope for This Plan

- **C-1 Track B** (replace pickle entirely) — architectural decision that affects the public DataStore protocol and requires a deprecation cycle. Tracked separately in the Phase 4 planning doc.
- **H-2 option 4** (remove `allow_callable_refs` from the public API) — breaking change; Phase 4 consideration.
