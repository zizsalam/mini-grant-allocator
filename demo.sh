#!/usr/bin/env bash
# =============================================================================
#  Agentic Grant Allocator — Automated Demo Script
#
#  Walks through every feature step by step with narration.
#  Press ENTER to advance each step. Start screen recording first.
#
#  Usage: ./demo.sh
# =============================================================================

set -euo pipefail
cd "$(dirname "$0")"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

step=0

narrate() {
  step=$((step + 1))
  echo ""
  echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  STEP ${step}: $1${NC}"
  echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

say() {
  echo -e "  ${CYAN}▸${NC} $1"
}

show_cmd() {
  echo ""
  echo -e "  ${DIM}\$${NC} ${GREEN}$1${NC}"
}

run_cmd() {
  show_cmd "$1"
  echo ""
  eval "$1" 2>&1 | sed 's/^/    /'
  echo ""
}

pause() {
  echo ""
  echo -e "  ${DIM}Press ENTER to continue...${NC}"
  read -r
}

open_browser() {
  if command -v open &>/dev/null; then
    open "$1"
  elif command -v xdg-open &>/dev/null; then
    xdg-open "$1"
  fi
}

# =============================================================================
#  PRE-FLIGHT
# =============================================================================

echo ""
echo -e "${BOLD}${PURPLE}"
echo "  ◆ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "    AGENTIC GRANT ALLOCATOR — LIVE DEMO"
echo "    Agentic Funding & Coordination Track"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ◆"
echo -e "${NC}"
echo ""
say "This script walks through the full system demo."
say "Start your screen recording, then press ENTER to begin."
pause

# =============================================================================
#  SCENE 1: Start Services
# =============================================================================

narrate "Launch Services"

say "Starting Dashboard (Flask :5050) and x402 API (Express :3000)..."

lsof -ti:5050 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

source .venv/bin/activate
python app.py &>/dev/null &
FLASK_PID=$!

cd solana
npx ts-node x402-server.ts &>/dev/null &
X402_PID=$!
cd ..

sleep 3

# Verify
DASH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/)
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/)

echo ""
echo -e "    ${GREEN}✓${NC} Dashboard:  http://localhost:5050  (${DASH_STATUS})"
echo -e "    ${GREEN}✓${NC} x402 API:   http://localhost:3000  (${API_STATUS})"
echo -e "    ${GREEN}✓${NC} Landing:    http://localhost:5050/demo"

trap "kill $FLASK_PID $X402_PID 2>/dev/null" EXIT

pause

# =============================================================================
#  SCENE 2: Landing Page
# =============================================================================

narrate "Landing Page — System Overview"

say "Opening the unified landing page..."
open_browser "http://localhost:5050/demo"
sleep 2

say "This page shows:"
say "  • 3-agent pipeline: Evaluator → Skeptic → Coordinator → Treasury → Ledger"
say "  • Three services: Dashboard, x402 Paid API, On-Chain Agents"
say "  • Registered Solana devnet addresses for both agents"
say "  • Full tech stack: Python, Claude Sonnet 4.6, HLOS/STAAMP, Solana, x402"

pause

# =============================================================================
#  SCENE 3: Run a Batch
# =============================================================================

narrate "Run Batch — 3-Agent Evaluation Panel"

say "Opening the dashboard..."
open_browser "http://localhost:5050"
sleep 2

say "Running 5 proposals through the 3-agent panel via CLI..."
say "(This calls Claude Sonnet 4.6 for all 3 agents per proposal = 15 LLM calls)"
echo ""

# Clear previous batch
rm -f ledger.json batch_report.json

source .venv/bin/activate
python -m src.main 2>&1 | while IFS= read -r line; do
  echo -e "    ${DIM}${line}${NC}"
done

say ""
say "Batch complete. Refreshing dashboard..."
open_browser "http://localhost:5050"

pause

# =============================================================================
#  SCENE 4: Examine Results
# =============================================================================

narrate "Dashboard — Score Comparison & Decisions"

say "Key things to notice in the dashboard:"
echo ""
echo -e "    ${GREEN}• Agent Score Chips${NC}: Each proposal shows Eval → Skep → Final scores"
echo -e "    ${PURPLE}• OVERRIDE badges${NC}: Where the Coordinator disagreed with the Evaluator"
echo -e "    ${RED}• Dimension failures${NC}: team, impact, budget, alignment, risk tags"
echo -e "    ${CYAN}• Balance tracking${NC}: Watch the wallet decrease with each approval"
echo -e "    ${YELLOW}• Receipt hashes${NC}: Every disbursement has a cryptographic receipt"
echo ""
say "The dashboard is live at http://localhost:5050"

pause

# =============================================================================
#  SCENE 5: Explainability
# =============================================================================

narrate "Explainability — Explain Any Decision From the Log Alone"

say "Let's explain the decision for PROP-001..."
echo ""
open_browser "http://localhost:5050/explain/PROP-001"
sleep 2

say "This explanation is generated entirely from the ledger — no LLM calls."
say "It shows:"
say "  • Agent panel scores (Evaluator, Skeptic, Final)"
say "  • Every dimension with PASS/FAIL against minimums"
say "  • Decision logic (which threshold was applied)"
say "  • Coordinator synthesis (how disagreements were resolved)"
say "  • Budget impact (balance before → after)"
echo ""

show_cmd "curl -s http://localhost:5050/explain/PROP-001"
echo ""
curl -s http://localhost:5050/explain/PROP-001 | sed 's/<[^>]*>//g' | head -30 | sed 's/^/    /'

pause

# =============================================================================
#  SCENE 6: Human Override
# =============================================================================

narrate "Human Override — Auditable Manual Intervention"

say "Overriding PROP-002 (rejected) to APPROVED via the API..."

run_cmd "curl -s -X POST http://localhost:5050/override/PROP-002 \
  -d 'decision=APPROVED&override_by=director&reason=Strategic+alignment+with+Q2+priorities' \
  -o /dev/null -w 'HTTP %{http_code} (redirect to dashboard)'"

say "The override is now visible in the dashboard:"
say "  • Orange 'HUMAN: director' badge on the row"
say "  • Override reason in the synthesis column"
say "  • Original decision preserved in the ledger for audit"
echo ""
say "Refreshing dashboard..."
open_browser "http://localhost:5050"

pause

# =============================================================================
#  SCENE 7: Observability Report
# =============================================================================

narrate "Observability Report — Tokens, Latency, Cost"

say "Opening the batch report..."
open_browser "http://localhost:5050/report"
sleep 2

say "The report tracks every agent invocation:"
say "  • Input/output tokens per call"
say "  • Latency in milliseconds"
say "  • Estimated LLM cost"
say "  • HLOS/STAAMP audit log (wallet ops + credential access)"
echo ""

# Show summary via API
show_cmd "curl -s http://localhost:5050/api/ledger | python3 -c \"import sys,json; d=json.load(sys.stdin); print(json.dumps(d['stats'], indent=2))\""
echo ""
curl -s http://localhost:5050/api/ledger | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['stats'], indent=2))" 2>/dev/null | sed 's/^/    /'

pause

# =============================================================================
#  SCENE 8: x402 Paid API
# =============================================================================

narrate "x402 Paid API — Pay-Per-Evaluation on Solana"

say "The evaluator is exposed as a paid API using the x402 protocol."
say "External agents POST a proposal and receive payment instructions."
echo ""

show_cmd "curl -s http://localhost:3000/"
echo ""
curl -s http://localhost:3000/ | python3 -m json.tool 2>/dev/null | sed 's/^/    /'
echo ""

say "Now requesting an evaluation without payment..."
echo ""
show_cmd "curl -s -X POST http://localhost:3000/evaluate -H 'Content-Type: application/json' -d '{\"proposal\":\"Build a water sensor network\"}'"
echo ""
curl -s -X POST http://localhost:3000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"proposal":"Build a water sensor network"}' | python3 -m json.tool 2>/dev/null | sed 's/^/    /'
echo ""

say "HTTP 402 — payment required. The response includes:"
say "  • Network: solana-devnet"
say "  • Amount: 0.10 USDC"
say "  • payTo: Treasury wallet address"
say "After payment, the request flows through to the Claude evaluator."

pause

# =============================================================================
#  SCENE 9: On-Chain Identity
# =============================================================================

narrate "On-Chain Identity — Solana Devnet"

say "Both agents are registered as Metaplex Core NFTs via the 8004 protocol."
echo ""

show_cmd "solana account HmMASnJ7WnUM6ZeasSus6G1cnZrmgbidh3GsgiEhtMfw --url devnet"
echo ""
solana account HmMASnJ7WnUM6ZeasSus6G1cnZrmgbidh3GsgiEhtMfw --url devnet 2>&1 | sed 's/^/    /'
echo ""

say "The account shows:"
say "  • Owned by the 8004 program (CoREEN...)"
say "  • Metadata URI → our agent description JSON"
say "  • ATOM reputation fields ready for feedback"
echo ""
say "Treasury agent also registered with operational wallet:"
echo ""
echo -e "    Evaluator: ${GREEN}HmMASnJ7WnUM6ZeasSus6G1cnZrmgbidh3GsgiEhtMfw${NC}"
echo -e "    Treasury:  ${GREEN}BPzvDy6nhPpo6afJs3tnfGndsafnmQ9jxvt6Hj6ws8xy${NC}"
echo -e "    Wallet:    ${GREEN}AWwdEEWBvtUNS4Tv5yNYh3XSjEAsA3L7ZySeW5WpUxZs${NC}"

pause

# =============================================================================
#  SCENE 10: Closing
# =============================================================================

narrate "Summary"

echo ""
echo -e "  ${BOLD}Agentic Grant Allocator${NC}"
echo ""
echo -e "  ${CYAN}Three AI agents${NC} evaluate proposals against a structured rubric."
echo -e "  ${GREEN}Treasury agent${NC} enforces hard budget constraints — no human in the loop."
echo -e "  ${YELLOW}Every decision${NC} is explainable from the audit log alone."
echo -e "  ${PURPLE}Both agents${NC} have verifiable on-chain identity on Solana."
echo -e "  ${RED}External agents${NC} can pay for evaluations via x402 protocol."
echo ""
echo -e "  ${DIM}Challenge Track:${NC} Agentic Funding & Coordination"
echo -e "  ${DIM}GitHub:${NC} https://github.com/zizsalam/mini-grant-allocator"
echo ""
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Demo complete. Stop your screen recording.${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
