#!/bin/bash
# ============================================================
# NWIS-Sentinel | SIH 2026 | One-Command Launcher
# Run this from: /workspaces/SIH_2026_PLANNS/
# Usage: bash start.sh
# ============================================================

set -e

cd "$(dirname "$0")/NLP/nlp_task_ddr"

echo ""
echo "======================================================================"
echo "     NWIS-Sentinel | SIH 2026 | PS SIH26121"
echo "======================================================================"
echo ""

# Always ensure all deps are installed (catches newly added packages)
echo "📦 Checking/installing dependencies..."
pip install --quiet -r ../../requirements.txt
echo "✅ Dependencies ready!"

echo ""
echo "🚀 Starting all modules via Gateway on port 5000..."
echo "   👉 After it starts, check the PORTS tab in VS Code sidebar"
echo "   👉 Click the globe 🌐 icon next to port 5000 to get your public URL"
echo ""

python gateway.py --no-browser --port 5000
