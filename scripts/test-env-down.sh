#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Stopping test services..."
docker compose -f "$REPO/docker-compose.test.yml" down -v

echo "==> Done."
