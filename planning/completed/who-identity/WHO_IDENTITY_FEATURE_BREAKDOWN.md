# Feature Breakdown — Run Identity Resolution (WHO)

**Status:** Ready for Implementation  
**Date:** 2026-05-19  
**Related:** `WHO_IDENTITY_PRD.md`, `WHO_IDENTITY_ADR.md`

---

## Overview

Twelve discrete tasks. Tasks 1–9 are sequential (each depends on the prior). Tasks 10–12 are parallel once Task 9 is merged.

---

## Task 1 — Extend `RunRequest` with `actor` and `trigger`

**File:** `pirn/engine/run_request.py`  
**Size:** XS (< 10 lines)  
**PRD:** F-1

Add two optional fields:

```python
actor: str | None = None
trigger: str | None = None
```

**Acceptance:** `RunRequest(actor="alice", trigger="cli")` constructs without error. Existing `RunRequest()` still works.

---

## Task 2 — `IdentityResolver` ABC

**File:** `pirn/core/identity/identity_resolver.py`  
**Size:** XS  
**PRD:** F-5

```python
from abc import ABC, abstractmethod

class IdentityResolver(ABC):
    @abstractmethod
    def resolve(self) -> str | None: ...
```

**Acceptance:** `isinstance` check works; cannot instantiate directly.

---

## Task 3 — `OsIdentityResolver`

**File:** `pirn/core/identity/os_identity_resolver.py`  
**Size:** XS  
**PRD:** F-6

```python
import getpass
from pirn.core.identity.identity_resolver import IdentityResolver

class OsIdentityResolver(IdentityResolver):
    def resolve(self) -> str | None:
        return getpass.getuser()
```

**Acceptance:** Returns a non-empty string on any OS.

---

## Task 4 — `EnvIdentityResolver`

**File:** `pirn/core/identity/env_identity_resolver.py`  
**Size:** S  
**PRD:** F-7

Constructor takes `vars: list[str]` with default `["GITHUB_ACTOR", "GITLAB_USER_LOGIN", "CI_USER", "BUILD_USER"]`. `resolve()` returns first non-empty env value, or `None`.

**Acceptance:** With `GITHUB_ACTOR=octocat` in env, returns `"octocat"`. With no matching vars set, returns `None`.

---

## Task 5 — `StaticIdentityResolver`

**File:** `pirn/core/identity/static_identity_resolver.py`  
**Size:** XS  
**PRD:** F-8

Constructor takes `actor: str`. `resolve()` returns it unconditionally.

**Acceptance:** Always returns the constructor value regardless of env or OS state.

---

## Task 6 — `ChainedIdentityResolver`

**File:** `pirn/core/identity/chained_identity_resolver.py`  
**Size:** XS  
**PRD:** F-9

Constructor takes `resolvers: list[IdentityResolver]`. `resolve()` iterates and returns first non-None result, or `None` if all return `None`.

**Acceptance:** Given `[NullIdentityResolver(), StaticIdentityResolver("x")]`, returns `"x"`.

---

## Task 7 — `NullIdentityResolver`

**File:** `pirn/core/identity/null_identity_resolver.py`  
**Size:** XS  
**PRD:** F-10

`resolve()` always returns `None`.

**Acceptance:** Useful in tests to suppress any resolution; always returns `None`.

---

## Task 8 — `__init__.py` for `pirn/core/identity/`

**File:** `pirn/core/identity/__init__.py`  
**Size:** XS

Re-export all six classes:

```python
from pirn.core.identity.identity_resolver import IdentityResolver
from pirn.core.identity.os_identity_resolver import OsIdentityResolver
from pirn.core.identity.env_identity_resolver import EnvIdentityResolver
from pirn.core.identity.static_identity_resolver import StaticIdentityResolver
from pirn.core.identity.chained_identity_resolver import ChainedIdentityResolver
from pirn.core.identity.null_identity_resolver import NullIdentityResolver

__all__ = [
    "IdentityResolver",
    "OsIdentityResolver",
    "EnvIdentityResolver",
    "StaticIdentityResolver",
    "ChainedIdentityResolver",
    "NullIdentityResolver",
]
```

**Acceptance:** `from pirn.core.identity import ChainedIdentityResolver` works.

---

## Task 9 — `Tapestry` constructor parameter

**File:** `pirn/tapestry.py`  
**Size:** S  
**PRD:** F-4

Add `identity_resolver: IdentityResolver | None = None` to `Tapestry.__init__`. When `None`, default to `ChainedIdentityResolver([EnvIdentityResolver(), OsIdentityResolver()])`.

**Acceptance:** `Tapestry()` works unchanged. `Tapestry(identity_resolver=NullIdentityResolver())` stores the resolver.

---

## Task 10 — Engine wiring

**File:** `pirn/engine/engine.py`  
**Size:** S  
**PRD:** F-2, F-3, F-11

In the method that constructs `RunContext` (currently hard-codes `actor=None`):

1. If `run_request.actor` is set → use it directly.
2. Otherwise → call `self._tapestry.identity_resolver.resolve()`.
3. Pass resolved actor and `run_request.trigger` into `RunContext`.
4. Ensure both flow through to `RunResult` and are persisted by history backends.

**Acceptance:** Running with no `RunRequest.actor` and `GITHUB_ACTOR=octocat` produces `run_result.actor == "octocat"`. Running locally with no env vars produces `run_result.actor == <os_username>`.

---

## Task 11 — Unit tests

**File:** `tests/unit/core/identity/test_*.py` (one file per class) + `tests/unit/core/identity/test_chaining.py`  
**Size:** M  
**PRD:** Acceptance criteria

| Test file | Covers |
|---|---|
| `test_os_identity_resolver.py` | Returns string, not None |
| `test_env_identity_resolver.py` | Known var present; no vars set; custom var list |
| `test_static_identity_resolver.py` | Returns fixed value unconditionally |
| `test_chained_identity_resolver.py` | First non-None wins; all-None returns None; explicit wins over chain |
| `test_null_identity_resolver.py` | Always returns None |
| `test_engine_identity.py` | RunRequest.actor overrides resolver; resolver result used when absent; NullResolver produces None actor |

**Acceptance:** `pytest tests/unit/core/identity/` passes. No existing tests broken.

---

## Task 12 — Explorer WHO display verification

**File:** `pirn/viz/explorer.py` (read-only verification)  
**Size:** XS  
**PRD:** F-12

The scanner already reads `actor` and `trigger` from the `runs` table (both present in the SELECT). Verify the explorer template renders both in the WHO row. If `trigger` is missing from the WHO row, add it alongside `actor`.

**Acceptance:** After running any example with the default resolver, the explorer's WHO field shows the OS username. `trigger` is displayed when set.

---

## Dependency Graph

```
Task 1 (RunRequest)
Task 2 (ABC)
  └── Tasks 3–7 (concrete resolvers)
        └── Task 8 (__init__.py)
              └── Task 9 (Tapestry param)
                    └── Task 10 (engine wiring)
                          ├── Task 11 (tests)
                          └── Task 12 (explorer verification)
```

---

## Estimated Total

| Size | Count | Rough LOC |
|---|---|---|
| XS | 8 | ~80 |
| S | 3 | ~60 |
| M | 1 | ~120 |
| **Total** | **12** | **~260** |
