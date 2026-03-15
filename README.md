# Agentic Grant Allocator

A fully autonomous grant allocation system where AI agents hold budgets, evaluate proposals, and disburse funds — with no human in the approval loop, verifiable on-chain identity, and a complete audit trail.

**Challenge Track:** Agentic Funding & Coordination

**GitHub:** [github.com/zizsalam/mini-grant-allocator](https://github.com/zizsalam/mini-grant-allocator)

---

## Demo

```bash
./start.sh
```

Opens two services:

| Service | URL | Description |
|---|---|---|
| **Dashboard** | [localhost:5050](http://localhost:5050) | Run batches, view scores, override decisions, explain outcomes |
| **Landing Page** | [localhost:5050/demo](http://localhost:5050/demo) | Unified overview with architecture, services, and on-chain agents |
| **x402 Paid API** | [localhost:3000](http://localhost:3000) | External agents pay 0.10 USDC per evaluation via Solana |

### Demo Walkthrough

1. Open [localhost:5050/demo](http://localhost:5050/demo) — see the full system overview
2. Click **Open Dashboard** — click **Run Batch** to evaluate 5 proposals with Claude
3. Watch the 3-agent panel: Evaluator scores, Skeptic challenges, Coordinator resolves
4. Click **Explain** on any proposal for a full plain-language breakdown
5. Click **Override** to simulate a human override with audit trail
6. Click **View Report** for observability data (tokens, latency, cost)
7. Visit [localhost:3000](http://localhost:3000) to see the x402 paid API

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      PROPOSAL BATCH (JSON)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    3-AGENT EVALUATION PANEL                       │
│                                                                   │
│   Evaluator ──▶ Skeptic ──▶ Coordinator                          │
│   (scores 0-100)  (challenges)  (resolves, final verdict)        │
│                                                                   │
│   All agents powered by Claude Sonnet 4.6                        │
│   Credentials via HLOS/STAAMP (agent never sees raw API keys)    │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                       TREASURY AGENT                              │
│                                                                   │
│   HLOS Wallet ──▶ Decision Engine ──▶ Append-Only Ledger         │
│   (hard budget)    (≥70:full, 50-69:   (every decision logged    │
│   (notarize +       partial, <50:       with reasoning trace     │
│    receipts)         reject)             + receipt hash)          │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    ON-CHAIN LAYER (Solana)                        │
│                                                                   │
│   Metaplex NFT Identity ──▶ x402 Paid API ──▶ ATOM Reputation   │
│   (8004-solana SDK)         (0.10 USDC/eval)   (on-chain track   │
│                                                  record)          │
└──────────────────────────────────────────────────────────────────┘
```

## Evaluation Rubric

| Dimension | What's Evaluated | Min to Pass |
|---|---|---|
| Team Credibility | Track record, expertise, delivery evidence | 10/20 |
| Impact Potential | Scale of problem, measurable outcomes | 12/20 |
| Budget Realism | Amount vs. scope, cost breakdown quality | 10/20 |
| Goal Alignment | Match with funding priorities | 12/20 |
| Execution Risk | Risks identified and mitigated | 8/20 |

**Thresholds:** ≥70 = full funding, 50-69 = partial (50-75%), <50 = reject. Any dimension below minimum = auto-reject.

---

## Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- Anthropic API key
- Solana CLI (for on-chain registration)

### Install

```bash
git clone https://github.com/zizsalam/mini-grant-allocator.git
cd mini-grant-allocator

# Python
python3 -m venv .venv
source .venv/bin/activate
pip install anthropic pydantic python-dotenv flask

# Solana
cd solana && npm install && cd ..

# Configure
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

### Run

```bash
# Everything at once
./start.sh

# Or individually
python app.py                    # Dashboard on :5050
cd solana && npm run server      # x402 API on :3000
python -m src.main               # CLI batch run
```

---

## On-Chain Agents (Solana Devnet)

Each agent is a Metaplex Core NFT registered via the `8004-solana` SDK:

| Agent | Asset Address | Role |
|---|---|---|
| **Evaluator** | `HmMASnJ7WnUM6ZeasSus6G1cnZrmgbidh3GsgiEhtMfw` | Scores proposals on 5-dimension rubric |
| **Treasury** | `BPzvDy6nhPpo6afJs3tnfGndsafnmQ9jxvt6Hj6ws8xy` | Budget enforcement + disbursement |
| **Treasury Wallet** | `AWwdEEWBvtUNS4Tv5yNYh3XSjEAsA3L7ZySeW5WpUxZs` | Operational wallet for payments |

Viewable on [8004market.io](https://8004market.io).

### x402 Paid API

External agents can request evaluations and pay per call:

```bash
# Without payment → 402 with instructions
curl -X POST localhost:3000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"proposal":"Build a water sensor network..."}'

# With payment proof → evaluation result
curl -X POST localhost:3000/evaluate \
  -H "Content-Type: application/json" \
  -H "x-payment-proof: <solana-tx-signature>" \
  -d '{"proposal":"Build a water sensor network..."}'
```

### ATOM Reputation

After each batch run, a quality score is submitted on-chain via ATOM feedback, building a tamper-proof track record of funding decision quality.

---

## HLOS / STAAMP Integration

The system implements STAAMP credential isolation — agents request capabilities, never hold raw API keys:

```
Agent Runtime                    HLOS Cloud
┌────────────────┐               ┌──────────────────┐
│ Evaluator      │               │ Passport (ID)    │
│ Skeptic        │──── STAAMP ──▶│ Wallet (limits)   │
│ Coordinator    │               │ Credentials (JIT) │
│ Treasury       │◀── receipts ──│ Audit trail       │
└────────────────┘               └──────────────────┘
```

Three integration modes: mock (default), `hlos run` (secret injection), direct API.

---

## Project Structure

```
mini-grant-allocator/
├── src/
│   ├── evaluator.py         # Agent 1: 5-dimension rubric scorer
│   ├── skeptic.py           # Agent 2: challenges evaluator
│   ├── coordinator.py       # Agent 3: resolves disagreements
│   ├── treasury.py          # Budget enforcement + disbursement
│   ├── hlos.py              # HLOS wallet + STAAMP layer
│   ├── staamp.py            # Credential isolation
│   ├── ledger.py            # Append-only decision log
│   ├── schemas.py           # Pydantic data models
│   ├── explainer.py         # Plain-language explanations
│   ├── observability.py     # Token/latency/cost tracking
│   └── main.py              # CLI batch pipeline
├── solana/
│   ├── register-agents.ts   # On-chain agent registration
│   ├── x402-server.ts       # Paid evaluation API
│   ├── feedback.ts          # ATOM reputation feedback
│   └── package.json
├── templates/
│   ├── demo.html            # Unified landing page
│   ├── index.html           # Dashboard
│   └── report.html          # Batch report
├── app.py                   # Flask web interface
├── start.sh                 # Unified launcher
└── data/sample_proposals.json
```

## Dashboard Features

| Feature | Endpoint | Description |
|---|---|---|
| Dashboard | `/` | Summary cards, agent scores, decision table |
| Landing Page | `/demo` | Architecture overview, all services linked |
| Run Batch | `POST /run` | Triggers 3-agent evaluation pipeline |
| Explain | `/explain/<id>` | Full decision breakdown from log alone |
| Override | `POST /override/<id>` | Human override with audit trail |
| Report | `/report` | Agent traces, HLOS audit, cost breakdown |
| API | `/api/ledger` | JSON endpoint |

---

## Challenge Track Alignment

**Track:** Agentic Funding & Coordination

> *What happens when agents can hold budgets, evaluate proposals, move capital, and make funding decisions?*

| Requirement | Implementation |
|---|---|
| **Agents hold budgets** | Treasury agent with HLOS wallet — hard balance enforcement |
| **Evaluate proposals** | 3-agent panel: evaluator + skeptic + coordinator (Claude Sonnet 4.6) |
| **Move capital** | `notarize()` disburses funds with cryptographic receipt hashes |
| **Make funding decisions** | Fully autonomous — score thresholds drive approve/partial/reject |
| **Clear rules** | 5-dimension rubric, dimension minimums, resubmission policy |
| **Verifiable outcomes** | Append-only ledger, HLOS audit trail, on-chain ATOM reputation, x402 receipts |

## Tech Stack

Python, Anthropic SDK (Claude Sonnet 4.6), HLOS/STAAMP, Flask, Solana (devnet), 8004-solana SDK, Metaplex Core, x402 Protocol, Pydantic
