#!/usr/bin/env bash
# ============================================================================
#  0_run_test.sh — Quick test for Python Sync
#  Version: 1.1.6 (Incremented for Wrapper Script)
# ============================================================================

# Define the path to the virtual environment python
# Use relative paths from script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${SCRIPT_DIR}/venv/bin/python"
SCRIPT_PATH="${SCRIPT_DIR}/0_main.py"

echo "[$(date)] INFO: Starting test sync for prefix EAR (Max: 1)..."

# Execute with a single record to verify logic
$PYTHON_BIN $SCRIPT_PATH --prefix "EAR" --max 1 --dry-run

# ============================================================================
# End of 0_run_test.sh — Version: 1.1.6
# ============================================================================
