#!/usr/bin/env bash
# Drops examples/pirn.db (if it exists) then re-runs every example script
# so the DB is rebuilt from scratch with fresh run history.
#
# Usage:
#   ./scripts/rebuild_examples_db.sh          # from repo root
#   bash scripts/rebuild_examples_db.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="$REPO_ROOT/examples/pirn.db"

# ---------------------------------------------------------------------------
# Drop
# ---------------------------------------------------------------------------
if [ -f "$DB_PATH" ]; then
    echo "Dropping $DB_PATH"
    rm "$DB_PATH"
else
    echo "No existing DB found — starting fresh"
fi

# ---------------------------------------------------------------------------
# Example entry points (order: core → financial → domain_formats → llm_agent)
# ---------------------------------------------------------------------------
EXAMPLES=(
    "examples/data_pipeline/simple_etl.py"
    "examples/data_pipeline/complex_analytics.py"
    "examples/lab_batch/lab_batch.py"
    "examples/content_moderation/run.py"
    "examples/document_analysis/document_analysis.py"
    "examples/pipeline_composition/sub_tapestry.py"
    "examples/software_execution/request_handler.py"
    "examples/software_execution/ci_pipeline.py"
    "examples/financial/fraud_detection.py"
    "examples/financial/loan_underwriting.py"
    "examples/domain_formats/weather_forecast_pipeline.py"
    "examples/domain_formats/geospatial_layer_analysis.py"
    "examples/domain_formats/ml_evaluation_loop.py"
    "examples/domain_formats/medical_triage_agent.py"
    "examples/domain_formats/seismic_survey_pipeline.py"
    "examples/domain_formats/genomics_batch_qc.py"
    "examples/domain_formats/hl7v2_message_router.py"
    "examples/llm_agent/agent_loop.py"
    "examples/llm_agent/agent_loop_v2.py"
    "examples/llm_agent/chatbot_pipeline.py"
)

# ---------------------------------------------------------------------------
# Run each example, collect pass/fail
# ---------------------------------------------------------------------------
PASS=()
FAIL=()

total=${#EXAMPLES[@]}
idx=0

for rel_path in "${EXAMPLES[@]}"; do
    idx=$((idx + 1))
    script="$REPO_ROOT/$rel_path"
    name="${rel_path#examples/}"
    printf "[%2d/%d] %-55s " "$idx" "$total" "$name"

    if output=$(python "$script" 2>&1); then
        echo "OK"
        PASS+=("$name")
    else
        echo "FAIL"
        echo "--- output ---"
        echo "$output" | tail -20
        echo "--------------"
        FAIL+=("$name")
    fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================="
echo "  Results: ${#PASS[@]} passed, ${#FAIL[@]} failed"
echo "========================================="
if [ ${#FAIL[@]} -gt 0 ]; then
    echo ""
    echo "Failed:"
    for f in "${FAIL[@]}"; do
        echo "  ✗ $f"
    done
    exit 1
fi
