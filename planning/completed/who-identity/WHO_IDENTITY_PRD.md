# PRD — Run Identity (WHO)

**Status:** Draft  
**Date:** 2026-05-19  
**Branch:** feat/update-lineage-capture-and-correct-examples  
**Author:** John Aven

---

## Problem Statement

Every pirn `RunResult` and `KnotLineage` record carries an `actor` field intended to answer "who triggered this run?" The field exists throughout the data model (`RunContext`, `RunResult`, the explorer's WHO row) but is **always `None`** in practice. `RunRequest` has no `actor` field, and the engine never resolves one.

This means the explorer's WHO row is always blank, lineage audits cannot attribute runs to people or services, and there is no way to filter or search history by actor.

The gap is structural: the model has the concept but there is no mechanism to populate it.

---

## Goals

1. Every run has a non-null `actor` that accurately reflects who or what initiated it.
2. Callers who know their identity (API handlers, CI jobs) can declare it explicitly.
3. Callers who do not declare it get a sensible auto-resolved value (OS user, CI env var, etc.).
4. The resolution strategy is pluggable — different deployment contexts can supply different resolvers without changing framework code.
5. `trigger` (the event or mechanism that caused the run) is captured alongside `actor`.

---

## Non-Goals

- Authentication or authorisation — pirn is not an auth system. `actor` is an informational attribution string, not a verified identity.
- Multi-tenancy or access control.
- Retroactive backfill of existing history records.

---

## User Stories

**Local developer**
> As a data engineer running pipelines locally, I want my OS username to appear in the explorer's WHO field automatically, without any configuration, so I can tell which runs were mine at a glance.

**CI pipeline**
> As a CI operator, I want the GitHub Actions actor (`GITHUB_ACTOR`) or the GitLab user (`GITLAB_USER_LOGIN`) to appear as the run actor, so I can trace failures back to the triggering commit/user.

**Production service**
> As a platform engineer deploying pirn as a backend service, I want to set a fixed service-account name as the actor for all runs from that service, so audit logs always show a stable identity.

**API-triggered run**
> As a web service developer, I want to pass the authenticated user's identity directly on `RunRequest`, so end-user attribution flows through to lineage without any resolver involvement.

**Explorer user**
> As someone reviewing run history in the explorer, I want every run to show a non-blank WHO value, and I want to be able to see `trigger` (e.g. `"webhook"`, `"schedule"`, `"cli"`) alongside it.

---

## Functional Requirements

| # | Requirement |
|---|-------------|
| F-1 | `RunRequest` accepts optional `actor: str \| None` and `trigger: str \| None` fields. |
| F-2 | When `RunRequest.actor` is set, it is used as-is — no resolver runs. |
| F-3 | When `RunRequest.actor` is absent, the engine calls `Tapestry.identity_resolver.resolve()` to obtain a value. |
| F-4 | `Tapestry` accepts an optional `identity_resolver` constructor argument; defaults to `ChainedIdentityResolver([EnvIdentityResolver(), OsIdentityResolver()])`. |
| F-5 | `IdentityResolver` is an abstract base class with a single `resolve() -> str \| None` method. |
| F-6 | `OsIdentityResolver` returns `getpass.getuser()`. |
| F-7 | `EnvIdentityResolver` accepts a list of env var names (default: `["GITHUB_ACTOR", "GITLAB_USER_LOGIN", "CI_USER", "BUILD_USER"]`); returns the first non-empty value found. |
| F-8 | `StaticIdentityResolver(actor)` returns a fixed string unconditionally. |
| F-9 | `ChainedIdentityResolver(resolvers)` tries each resolver in order, returns the first non-None result. |
| F-10 | `NullIdentityResolver` always returns `None` (useful in tests to suppress any resolution). |
| F-11 | Resolved actor and trigger are stored in `RunContext`, flow into `RunResult`, and are persisted by history backends. |
| F-12 | The explorer's WHO row displays the actor and trigger (when present) for every run. |

---

## Out of Scope for v1

- User-facing configuration file (e.g. `pirn.toml`) for default actor — can be added later by wrapping `StaticIdentityResolver`.
- Async resolvers (e.g. resolving from a token introspection endpoint) — `resolve()` is synchronous in v1.
- Per-knot actor attribution.

---

## Acceptance Criteria

- [ ] Running any example locally with no `identity_resolver` set shows the OS username in the explorer WHO field.
- [ ] Setting `GITHUB_ACTOR=octocat` in env and running a pipeline shows `actor="octocat"` in the run result.
- [ ] Passing `RunRequest(actor="alice@example.com")` overrides any resolver; `actor` in history is `"alice@example.com"`.
- [ ] `Tapestry(identity_resolver=StaticIdentityResolver("svc-ingest"))` sets `actor="svc-ingest"` on every run.
- [ ] `Tapestry(identity_resolver=NullIdentityResolver())` results in `actor=None` in the run (existing behaviour preserved for opt-out).
- [ ] All existing tests continue to pass with no changes to test code.
- [ ] New unit tests cover each resolver class and the chaining behaviour.
