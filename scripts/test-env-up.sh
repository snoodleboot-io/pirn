#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Starting test services..."
docker compose -f "$REPO/docker-compose.test.yml" up -d

echo "==> Waiting for services to be healthy..."
for service in postgres valkey minio; do
    echo -n "    $service: "
    for i in $(seq 1 30); do
        status=$(docker compose -f "$REPO/docker-compose.test.yml" ps --format json "$service" 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health','') or d.get('State',''))" 2>/dev/null || echo "starting")
        if [[ "$status" == "healthy" || "$status" == "running" ]]; then
            echo "ready"
            break
        fi
        if [[ $i -eq 30 ]]; then
            echo "timed out"
        fi
        sleep 1
    done
done

echo "==> Creating MinIO bucket..."
docker run --rm --network host minio/mc \
    alias set local http://localhost:9000 pirn pirntestpassword --quiet 2>/dev/null || true
docker run --rm --network host minio/mc \
    mb local/pirn-test --quiet 2>/dev/null || true

echo "==> Exporting env vars..."
export PIRN_TEST_POSTGRES_URL="postgresql://pirn:pirn@localhost:5433/pirn_test"
export PIRN_TEST_VALKEY_URL="redis://localhost:6380/0"
export PIRN_TEST_KAFKA_URL="localhost:9092"
export PIRN_TEST_S3_ENDPOINT="http://localhost:9000"
export PIRN_TEST_S3_ACCESS_KEY="pirn"
export PIRN_TEST_S3_SECRET_KEY="pirntestpassword"
export PIRN_TEST_S3_BUCKET="pirn-test"

echo ""
echo "==> Services up. Run tests with:"
echo ""
echo "    source scripts/test-env-up.sh && uv run pytest -q"
echo ""
echo "    or for real-backend tests only:"
echo ""
echo "    source scripts/test-env-up.sh && uv run pytest -q -m 'needs_postgres or needs_valkey or needs_s3 or needs_kafka'"
