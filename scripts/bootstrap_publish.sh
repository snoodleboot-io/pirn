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

if [ -n "${PYPI_TOKEN:-}" ]; then
  echo ">> Uploading to ${INDEX} (${REPO_URL}) using PYPI_TOKEN env var"
  TWINE_USERNAME=__token__ TWINE_PASSWORD="$PYPI_TOKEN" \
    uvx twine upload --repository-url "$REPO_URL" --non-interactive --disable-progress-bar dist/*
else
  echo ">> Uploading to ${INDEX} using ~/.pypirc section [${INDEX}]"
  uvx twine upload --repository "$INDEX" --non-interactive --disable-progress-bar dist/*
fi

echo ">> Done. The 7 projects now exist on ${INDEX}."
echo ">> Next: add a Trusted Publisher to each project (repo=snoodleboot-io/pirn,"
echo "   workflow=publish.yml, environment=${INDEX}), then releases use OIDC."
