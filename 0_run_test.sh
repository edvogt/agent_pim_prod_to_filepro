#!/usr/bin/env bash
# ============================================================================
#  0_run_test.sh — Quick test for Python Sync
#  Version: 1.1.6 (Incremented for Wrapper Script)
# ============================================================================

# Define the path to the virtual environment python
PYTHON_BIN="/var/www/html/agent_pimcore_push_to_shopify/venv/bin/python"
SCRIPT_PATH="/var/www/html/agent_pimcore_push_to_shopify/0_main.py"

echo "[$(date)] INFO: Starting test sync for prefix EAR (Max: 1)..."

# Execute with a single record to verify logic
$PYTHON_BIN $SCRIPT_PATH --prefix "EAR" --max 1 --dry-run

# ============================================================================
# End of 0_run_test.sh — Version: 1.1.6
# ============================================================================
