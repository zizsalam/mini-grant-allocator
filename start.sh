#!/usr/bin/env bash
# =============================================================================
#  Agentic Grant Allocator — Unified Launcher
#  Starts both the Dashboard (Flask :5050) and x402 API (Express :3000)
# =============================================================================

set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "  ◆ Agentic Grant Allocator"
echo "  ════════════════════════════════════════"
echo ""

# Kill any existing instances
lsof -ti:5050 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Start Flask dashboard
echo "  Starting Dashboard (Flask :5050)..."
source .venv/bin/activate
python app.py &
FLASK_PID=$!

# Start x402 server
echo "  Starting x402 Paid API (Express :3000)..."
cd solana
npx ts-node x402-server.ts &
X402_PID=$!
cd ..

sleep 3

echo ""
echo "  ════════════════════════════════════════"
echo "  ◆ All services running"
echo ""
echo "    Dashboard:    http://localhost:5050"
echo "    x402 API:     http://localhost:3000"
echo "    Health:       http://localhost:3000/health"
echo ""
echo "    Evaluator:    HmMASnJ7WnUM6ZeasSus6G1cnZrmgbidh3GsgiEhtMfw"
echo "    Treasury:     BPzvDy6nhPpo6afJs3tnfGndsafnmQ9jxvt6Hj6ws8xy"
echo "    Network:      Solana Devnet"
echo ""
echo "    GitHub:       https://github.com/zizsalam/mini-grant-allocator"
echo "  ════════════════════════════════════════"
echo ""
echo "  Press Ctrl+C to stop all services"
echo ""

# Wait for either process to exit
trap "kill $FLASK_PID $X402_PID 2>/dev/null; echo '  Stopped.'" EXIT
wait
