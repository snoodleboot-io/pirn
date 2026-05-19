# ADR — Run Identity Resolution

**Status:** Proposed  
**Date:** 2026-05-19  
**Deciders:** John Aven  
**Related PRD:** `WHO_IDENTITY_PRD.md`

---

## Context

The `actor` field exists on `RunContext` and `RunResult` but is never populated. `RunRequest` carries no identity fields. The engine hard-codes `actor=None` when constructing `RunContext`. There is no mechanism for the framework to auto-resolve identity, and no hook for deployment contexts to supply their own strategy.

The core tension is between two valid approaches:

1. **Caller responsibility only** — require every caller to set `actor` on `RunRequest` explicitly. Simple, no magic.
2. **Framework-level resolution with pluggable strategy** — the framework auto-resolves when the caller doesn't declare, using a swappable `IdentityResolver`.

Option 1 leaves the field blank for any caller that doesn't think to set it (which is all existing callers). Option 2 gives sensible defaults while still allowing explicit override.

---

## Decision

**Adopt a two-layer model:**

1. `RunRequest.actor` (and `.trigger`) — explicit, always authoritative when set.
2. `IdentityResolver` on `Tapestry` — auto-resolve fallback when `RunRequest.actor` is absent.

The engine checks `RunRequest.actor` first. If absent, it calls `tapestry.identity_resolver.resolve()`. If the resolver also returns `None`, `actor` remains `None` (no hard failure).

`IdentityResolver` is an **interface-style base class** following pirn's convention (`raise NotImplementedError`, not ABC/abstractmethod) because:
- Consistent with `DataTransport`, `RunHistory`, `Assembler`, `Disassembler`, and all other pirn base classes.
- `isinstance` checks work identically — all concrete classes inherit from `IdentityResolver`.
- Concrete implementations can share utility logic via the base class in future.

---

## Alternatives Considered

### A. Caller-only (no framework resolution)

Add `actor`/`trigger` to `RunRequest` but provide no auto-resolver.

**Pro:** Simplest. No framework magic. Explicit is always clear.  
**Con:** Every existing call site stays blank. New users have to discover the field. Local dev runs and CI jobs never get attribution without boilerplate.  
**Rejected:** The gap is too wide — all current history is unattributed.

---

### B. Framework reads env vars directly (no abstraction)

Engine calls `os.environ.get("GITHUB_ACTOR") or getpass.getuser()` inline.

**Pro:** Zero configuration, works for common cases immediately.  
**Con:** Hardcodes strategy in framework code. Services that don't want OS-user attribution cannot opt out cleanly. Violates Open/Closed — adding a new source requires editing the engine.  
**Rejected:** Not extensible enough.

---

### C. Global registry / singleton resolver

A module-level `set_identity_resolver(resolver)` that applies to all `Tapestry` instances.

**Pro:** No per-tapestry wiring.  
**Con:** Global mutable state is hard to test and creates surprising action at a distance. Two tapestries in the same process could not have different resolvers. Violates DI principles.  
**Rejected:** Anti-pattern.

---

### D. Async resolver interface

`resolve()` is `async`, allowing resolvers that fetch identity from a token endpoint.

**Pro:** Supports richer identity sources (OAuth introspection, Vault, etc.).  
**Con:** Forces async call path through `RunContext` construction, which is currently synchronous. Adds complexity for a use case that can be served by injecting the identity externally (`RunRequest.actor`) without a resolver.  
**Deferred:** Can be revisited in v2. External callers who have async identity can await it before constructing `RunRequest`.

---

## Consequences

**Positive:**
- All existing call sites get OS-user attribution immediately with no code changes.
- CI pipelines get actor from env vars automatically.
- Services can supply a `StaticIdentityResolver` at `Tapestry` construction — one line.
- API handlers can pass authenticated user identity directly on `RunRequest` — no resolver needed.
- Fully testable: `NullIdentityResolver` suppresses all resolution; `StaticIdentityResolver` gives deterministic values.

**Negative / Trade-offs:**
- One new constructor parameter on `Tapestry` (`identity_resolver`). Existing code is unaffected (defaults to chained env+OS resolver).
- The default resolver reads env vars, which could surface unexpected values in unusual environments. Mitigated by: (a) env vars are widely understood, (b) `NullIdentityResolver` is available for opt-out.

---

## Resolution Order (Default Chain)

```
RunRequest.actor          ← explicit, highest priority
  └── EnvIdentityResolver ← GITHUB_ACTOR, GITLAB_USER_LOGIN, CI_USER, BUILD_USER
        └── OsIdentityResolver ← getpass.getuser()
              └── None    ← no attribution (no hard failure)
```

---

## Interface Contract

```python
class IdentityResolver(ABC):
    @abstractmethod
    def resolve(self) -> str | None:
        """Return an actor string or None if identity cannot be determined."""
        ...
```

All built-in implementations:

| Class | Behaviour |
|---|---|
| `OsIdentityResolver` | `getpass.getuser()` |
| `EnvIdentityResolver(vars)` | First non-empty value from env var list |
| `StaticIdentityResolver(actor)` | Fixed string |
| `ChainedIdentityResolver(resolvers)` | First non-None result from chain |
| `NullIdentityResolver` | Always `None` |

---

## File Locations

Following the one-class-per-file convention:

```
pirn/core/identity/
    identity_resolver.py          ← ABC
    os_identity_resolver.py
    env_identity_resolver.py
    static_identity_resolver.py
    chained_identity_resolver.py
    null_identity_resolver.py
    __init__.py                   ← re-exports all
```
