#!/usr/bin/env bash
# One-time bootstrap: build all 7 wheels + sdists and upload them with an
# account-scoped API TOKEN to CREATE the PyPI / TestPyPI projects.
#
# Why: pending trusted publishers must be unique per (repo+workflow+environment),
# so you can't pre-register all 7. Once the projects EXIST (this script), you add
# a Trusted Publisher to each one (all can share publish.yml + the pypi/testpypi
# environment), then future releases go through OIDC via publish.yml — token done.
#
# Usage (TestPyPI first to validate, then PyPI):
# Credentials, in order of preference:
#   1. ~/.pypirc  (default) — needs a [pypi] and a [testpypi] section, e.g.:
#        [testpypi]
#        repository = https://test.pypi.org/legacy/
#        username = __token__
#        password = pypi-...
#   2. PYPI_TOKEN env var (override) — used if set, ignores ~/.pypirc.
#
# Usage (TestPyPI first to validate, then PyPI):
#   ./scripts/bootstrap_publish.sh testpypi
#   ./scripts/bootstrap_publish.sh pypi
#   # or, to override .pypirc with an explicit token:
#   PYPI_TOKEN='pypi-XXetc' ./scripts/bootstrap_publish.sh pypi
#
# The version uploaded is whatever is stamped in the pyprojects (currently
# 0.4.0); to pick a different first version run
# scripts/stamp_workspace_version.py --version X.Y.Z first.
# NOTE: a version, once uploaded to PyPI, can never be reused.
set -euo pipefail

INDEX="${1:?usage: bootstrap_publish.sh <testpypi|pypi>}"

case "$INDEX" in
  testpypi) REPO_URL="https://test.pypi.org/legacy/" ;;
  pypi)     REPO_URL="https://upload.pypi.org/legacy/" ;;
  *) echo "index must be 'testpypi' or 'pypi'" >&2; exit 2 ;;
esac

PACKAGES="pirn-core pirn-signal pirn-data pirn-ml pirn-agents pirn-health pirn-oilgas"

echo ">> Building wheels + sdists for 7 packages..."
rm -rf dist
for p in $PACKAGES; do
  uv build "packages/$p" -o dist/
done
echo ">> Built:"; ls -1 dist/

# --skip-existing makes every upload idempotent (already-present files/projects
# are skipped), so this is safe to re-run to finish anything that was 429'd.
upload() {  # upload <files...>
  if [ -n "${PYPI_TOKEN:-}" ]; then
    TWINE_USERNAME=__token__ TWINE_PASSWORD="$PYPI_TOKEN" \
      uvx twine upload --repository-url "$REPO_URL" --skip-existing --non-interactive --disable-progress-bar "$@"
  else
    uvx twine upload --repository "$INDEX" --skip-existing --non-interactive --disable-progress-bar "$@"
  fi
}

# Which projects still need creating (skip ones already live).
JSON_BASE="https://pypi.org/pypi"; [ "$INDEX" = testpypi ] && JSON_BASE="https://test.pypi.org/pypi"
todo=""
for p in $PACKAGES; do
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$JSON_BASE/$p/json")" = "200" ] || todo="$todo $p"
done
todo="${todo# }"
if [ -z "$todo" ]; then echo ">> All 7 already live on ${INDEX}. Nothing to do."; exit 0; fi
echo ">> Need to upload:${todo:+ }$todo"

# PACE_SECONDS > 0 → upload ONE project at a time with a gap, so each new-project
# creation fits inside PyPI's rate-limit window (PyPI 429s bursts of new projects).
# Default 0 = bulk. Recommended for a fresh PyPI bootstrap: PACE_SECONDS=900.
PACE="${PACE_SECONDS:-0}"
if [ "$PACE" -gt 0 ] 2>/dev/null; then
  echo ">> Paced mode: one project every ${PACE}s, ${RETRIES:-4} retries each"
  first=1
  for p in $todo; do
    fn=$(echo "$p" | tr - _)
    if [ "$first" = 0 ]; then echo ">> sleeping ${PACE}s before ${p}..."; sleep "$PACE"; fi
    first=0
    ok=0
    for a in $(seq 1 "${RETRIES:-4}"); do
      echo ">> uploading ${p} (attempt ${a})"
      if upload dist/${fn}-*; then ok=1; break; fi
      echo "   ${p} 429/error; backing off 180s"; sleep 180
    done
    [ "$ok" = 1 ] || echo "::warning:: ${p} still not uploaded (rate-limited) — re-run later"
  done
else
  echo ">> Bulk upload (set PACE_SECONDS=900 to pace one project at a time)"
  upload dist/*
fi

echo ">> Final ${INDEX} status:"
for p in $PACKAGES; do
  echo "   $p: $(curl -s -o /dev/null -w '%{http_code}' "$JSON_BASE/$p/json")"
done
echo ">> When all are live: add a Trusted Publisher per project"
echo "   (repo=snoodleboot-io/pirn, workflow=publish.yml, environment=${INDEX})."
