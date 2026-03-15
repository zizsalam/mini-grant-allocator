# Agentic Grant Allocator

A fully autonomous grant allocation system where AI agents hold budgets, evaluate proposals, and disburse funds — with no human in the approval loop.

Built for the **Agentic Funding & Coordination** challenge track.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    PROPOSAL BATCH (JSON)                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   3-AGENT EVALUATION PANEL                   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  EVALUATOR   │  │   SKEPTIC    │  │   COORDINATOR     │  │
│  │              │  │              │  │                   │  │
│  │ Scores each  │─▶│ Challenges   │─▶│ Resolves conflict │  │
│  │ proposal on  │  │ scores, flags│  │ issues final      │  │
│  │ 5-dimension  │  │ weaknesses & │  │ verdict with      │  │
│  │ rubric       │  │ risks        │  │ synthesis         │  │
│  │ (0-100)      │  │              │  │ reasoning         │  │
│  └──────────────┘  └──────────────┘  └───────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     TREASURY AGENT                           │
│                                                              │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ HLOS Wallet    │  │  Decision    │  │ Append-Only     │  │
│  │                │  │  Engine      │  │ Ledger          │  │
│  │ Balance check  │  │              │  │                 │  │
│  │ Hard budget    │  │ ≥70: Full    │  │ Every decision  │  │
│  │ enforcement    │  │ 50-69: Part  │  │ logged with     │  │
│  │ notarize() +   │  │ <50: Reject  │  │ reasoning trace │  │
│  │ receipt hash   │  │              │  │ + receipt hash  │  │
│  └────────────────┘  └──────────────┘  └─────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     WEB DASHBOARD                            │
│                                                              │
│  Summary Cards │ Agent Score Comparison │ Explain │ Override  │
│  Batch Report  │ HLOS Audit Log        │ Observability       │
└─────────────────────────────────────────────────────────────┘
```

## Evaluation Rubric

Each proposal is scored on 5 dimensions (0-20 each, 100 total):

| Dimension | What's Evaluated | Min to Pass |
|---|---|---|
| Team Credibility | Track record, expertise, delivery evidence | 10 |
| Impact Potential | Scale of problem, measurable outcomes | 12 |
| Budget Realism | Amount vs. scope, cost breakdown quality | 10 |
| Goal Alignment | Match with funding priorities | 12 |
| Execution Risk | Risks identified and mitigated | 8 |

**Decision thresholds:** ≥70 = full funding, 50-69 = partial (50-75%), <50 = reject. Any dimension below minimum = auto-reject.

## HLOS / STAAMP Integration

The system implements the STAAMP credential isolation pattern:

- **Agent = merchant terminal** — makes funding decisions
- **HLOS = payment network** — enforces budget constraints
- **Wallet balance = credit line** — hard limit, not advisory
- **Credentials** — agents request capabilities, never hold raw API keys

```
Agent Runtime                    HLOS Cloud
┌────────────────┐               ┌─────────────────┐
│ Evaluator      │               │ Passport (ID)   │
│ Skeptic        │──── STAAMP ──▶│ Wallet (limits)  │
│ Coordinator    │               │ Credentials (JIT)│
│ Treasury       │◀── receipts ──│ Audit trail      │
└────────────────┘               └─────────────────┘
        │
   Never sees raw
   API keys or
   credentials
```

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+ (for HLOS CLI)
- Anthropic API key

### Setup

```bash
# Clone and enter project
cd mini-grant-allocator

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install anthropic pydantic python-dotenv flask

# Configure
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Install HLOS CLI
npm install -g @hlos/cli
```

### Run via CLI

```bash
python -m src.main
```

### Run via Web Dashboard

```bash
python app.py
# Open http://localhost:5050
```

### Run with HLOS Credential Isolation

```bash
# Store API key in HLOS vault (when HLOS supports write)
hlos secrets set ANTHROPIC_API_KEY=<your-key>

# Run with secrets injected at runtime — never written to disk
hlos run -- python -m src.main
```

### Verify HLOS Setup

```bash
python verify_hlos.py
```

## Project Structure

```
mini-grant-allocator/
├── src/
│   ├── evaluator.py       # Agent 1: scores proposals against rubric
│   ├── skeptic.py         # Agent 2: challenges evaluator's scores
│   ├── coordinator.py     # Agent 3: resolves disagreements, final verdict
│   ├── treasury.py        # Budget enforcement + disbursement
│   ├── hlos.py            # HLOS wallet + STAAMP integration
│   ├── staamp.py          # Credential isolation for all agents
│   ├── ledger.py          # Append-only decision log (atomic writes)
│   ├── schemas.py         # Pydantic data models
│   ├── explainer.py       # Plain-language decision explanations
│   ├── observability.py   # Token/latency/cost tracking
│   └── main.py            # CLI batch pipeline
├── templates/
│   ├── index.html         # Dashboard with scores, overrides, explain
│   └── report.html        # Batch report with observability data
├── data/
│   └── sample_proposals.json  # 5 test proposals (2 strong, 1 mid, 2 weak)
├── app.py                 # Flask web interface
├── verify_hlos.py         # HLOS setup checklist verification
├── hlos_setup.sh          # HLOS CLI setup script
├── hlos.yaml              # HLOS space config
├── .claude/mcp.json       # MCP server config for Claude Desktop/Cursor
├── pyproject.toml
├── .env.example
└── .gitignore
```

## Web Dashboard Features

| Feature | Endpoint | Description |
|---|---|---|
| Dashboard | `/` | Summary cards, proposal table, agent score comparison |
| Run Batch | `POST /run` | Triggers full 3-agent evaluation pipeline |
| Explain | `/explain/<id>` | Plain-language decision breakdown |
| Override | `POST /override/<id>` | Human override with audit trail |
| Report | `/report` | Agent traces, HLOS audit log, cost breakdown |
| API | `/api/ledger` | JSON endpoint for programmatic access |

## Challenge Track Alignment

**Track:** Agentic Funding & Coordination

| Requirement | Implementation |
|---|---|
| Agents hold budgets | Treasury agent with HLOS wallet — hard balance enforcement |
| Evaluate proposals | 3-agent panel with structured rubric (evaluator + skeptic + coordinator) |
| Move capital | `notarize()` disburses funds with cryptographic receipt hashes |
| Make funding decisions | Fully autonomous — score thresholds drive approve/partial/reject |
| Clear rules | 5-dimension rubric, dimension minimums, resubmission policy |
| Verifiable outcomes | Append-only ledger, receipt hashes, HLOS audit trail, per-decision explainability |

## Tech Stack

- **Python** — core runtime
- **Anthropic SDK** (Claude Sonnet 4.6) — powers all 3 evaluation agents
- **HLOS / STAAMP** — credential isolation + wallet infrastructure
- **Flask** — web dashboard
- **Pydantic** — data validation and schemas

## Phased Build

| Phase | Deliverable |
|---|---|
| Phase 1 | Evaluator agent — structured JSON scoring with 5-dimension rubric |
| Phase 2 | Treasury agent — HLOS wallet, budget enforcement, ledger, receipts |
| Phase 3 | 3-agent panel — skeptic + coordinator, disagreement resolution, resubmission detection |
| Phase 4 | Observability, explainability, human override, batch reports, HLOS/STAAMP integration |
