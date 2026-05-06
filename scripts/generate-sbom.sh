#!/usr/bin/env bash
# Generate a CycloneDX SBOM for the pirn package + its currently-installed
# dependencies. Output is written to ``sbom/pirn-{date}-{git-sha}.cdx.json``.
#
# Intended for CI: run on every release tag to capture the dependency
# graph as it shipped, and on pre-merge to spot newly-introduced
# transitive vulnerabilities (combined with ``pip-audit`` below).
#
# Usage:
#   scripts/generate-sbom.sh             # current venv
#   scripts/generate-sbom.sh --extras all  # install [all] extras first
#
# Requires ``cyclonedx-bom`` (declared in the ``dev`` extra) and
# ``pip-audit`` (recommended for vuln scanning).

set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v cyclonedx-py >/dev/null 2>&1; then
    echo "cyclonedx-py not found. Install via:"
    echo "  uv pip install cyclonedx-bom"
    exit 1
fi

EXTRAS=""
if [[ "${1:-}" == "--extras" && -n "${2:-}" ]]; then
    EXTRAS="$2"
    echo "Installing pirn[$EXTRAS] before generating SBOM..."
    uv pip install -e ".[$EXTRAS]"
fi

mkdir -p sbom

DATE="$(date +%Y-%m-%d)"
SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
OUT="sbom/pirn-${DATE}-${SHA}.cdx.json"

echo "Generating SBOM -> $OUT"
cyclonedx-py environment --output-format JSON --output-file "$OUT"

echo "SBOM written to $OUT"
echo

# Optional vuln scan if pip-audit is available.
if command -v pip-audit >/dev/null 2>&1; then
    echo "Running pip-audit against the current environment..."
    pip-audit || {
        echo "pip-audit reported vulnerabilities — review before release."
        exit 2
    }
else
    echo "pip-audit not installed; skip vuln scan."
    echo "  Install with: uv pip install pip-audit"
fi
