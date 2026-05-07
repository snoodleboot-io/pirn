---
session_id: "session_20260506_ci7x3q"
branch: "feat/ci-ghcr-build-cache"
created_at: "2026-05-06T00:00:00Z"
current_mode: "devops"
version: "1.0"
---

## Session Overview

**Branch:** feat/ci-ghcr-build-cache
**Started:** 2026-05-06 UTC
**Current Mode:** devops

## Mode History

| Mode | Entered | Exited | Summary |
|------|---------|--------|---------|
| devops | 2026-05-06 | - | CI optimization: GHCR base image + lint gating + job ordering |

## Actions Taken

### 2026-05-06 — devops mode
- Analyzed ci.yml: identified apt-get duplication across ~6 jobs, lint/test running in parallel, 32+ matrix jobs starting cold
- Plan agreed: Dockerfile.ci + build-ci-image.yml + rewrite ci.yml

## Context Summary

**Goal:** Three CI optimizations:
1. Pre-built GHCR base image `pirn-ci-base` with all apt deps baked in
2. lint gates unit-tests; unit-tests gates all matrix/integration/smoke jobs
3. All native-lib jobs switch from apt-get to container image

**Image name:** `ghcr.io/${{ github.repository_owner }}/pirn-ci-base:latest`
**Trigger:** Dockerfile.ci changes + workflow_dispatch (no weekly schedule)

**Files to create/modify:**
- `Dockerfile.ci` (new)
- `.github/workflows/build-ci-image.yml` (new)
- `.github/workflows/ci.yml` (modify)

## Notes
- No ticket ID — branch named feat/ci-ghcr-build-cache by user direction
- connector-extras-matrix and perf-tests do NOT need native libs — skip container for those
