# Demo Video Outline — Agentic Grant Allocator

**Target length:** 3–4 minutes
**Record with:** Screen capture (QuickTime/Loom) + voiceover

---

## SCENE 1: Hook (15 sec)

**Show:** Landing page at `localhost:5050/demo`

**Say:**
> "What happens when AI agents can hold real budgets and make funding decisions autonomously? This is the Agentic Grant Allocator — a system where three AI agents evaluate grant proposals, enforce budget constraints, and disburse funds with a complete audit trail. Every agent has a verifiable on-chain identity on Solana."

**Action:** Scroll the landing page slowly — show the architecture flow, service cards, and on-chain agent addresses.

---

## SCENE 2: Run a Batch (60 sec)

**Show:** Click "Open Dashboard" → Dashboard at `localhost:5050`

**Say:**
> "Let's run a batch of 5 proposals through the system."

**Action:** Click **Run Batch**. While loading spinner shows:

> "Three agents work in sequence. The Evaluator scores each proposal on a 5-dimension rubric — team credibility, impact potential, budget realism, goal alignment, and execution risk. The Skeptic then challenges those scores, looking for overstatements and missing evidence. Finally, the Coordinator resolves disagreements and issues the final verdict."

**When results appear, point out:**
- Summary cards: "2 approved, 3 rejected, $5,100 disbursed out of $10,000"
- Agent score chips: "Here you can see the Evaluator gave PROP-001 an 83, the Skeptic knocked it down to 68, and the Coordinator settled on 74 — that's an override"
- A rejected proposal: "PROP-002 scored 22 — both agents agreed it was too vague, no team, no budget breakdown"
- The balance card: "Budget enforcement is a hard constraint. When it hits zero, no more approvals."

---

## SCENE 3: Explainability (30 sec)

**Show:** Click **Explain** on PROP-001 (or any approved proposal)

**Say:**
> "Any decision can be fully explained from the ledger alone, without re-running the agents."

**Action:** Scroll through the explanation page. Highlight:
- Agent panel scores (Evaluator → Skeptic → Final)
- Dimension breakdown with PASS/FAIL per dimension
- Decision logic: "Score 74 is in the partial funding range"
- Coordinator synthesis: the actual reasoning
- Budget impact: balance before and after

> "This is generated entirely from the audit log — not from the LLM. It's deterministic and reproducible."

---

## SCENE 4: Human Override (20 sec)

**Show:** Back on dashboard. Click **Override** on a rejected proposal.

**Say:**
> "Humans can override any agent decision. The override is itself an auditable event."

**Action:**
- Select "APPROVED" from dropdown
- Type name: "admin"
- Type reason: "Funded via director's discretion — strong alignment with Q2 priorities"
- Click **Apply Override**

**Point out:** The orange "HUMAN: admin" badge appears on the row, and the override reason shows in the synthesis column.

---

## SCENE 5: Observability Report (20 sec)

**Show:** Click **View Report**

**Say:**
> "Every agent call is tracked — input tokens, output tokens, latency, estimated cost."

**Action:** Scroll through:
- Agent traces table: "15 agent calls across 5 proposals"
- HLOS audit log: "Every wallet operation is logged — balance checks, disbursements, credential access"
- Cost summary: "Total LLM cost for this batch"

---

## SCENE 6: x402 Paid API (30 sec)

**Show:** Open `localhost:3000` in a new tab

**Say:**
> "The evaluator is also exposed as a paid API using the x402 protocol. External agents can POST a proposal and get payment instructions — 10 cents in USDC on Solana per evaluation."

**Action:** Show the JSON response with pricing and agent addresses. Then switch to terminal:

```bash
curl -X POST localhost:3000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"proposal":"test"}'
```

**Point out:** The 402 response with `payTo` wallet address and USDC amount.

> "After payment, the request flows through to the same Claude-powered evaluator and returns the structured score. The treasury wallet receives the payment automatically."

---

## SCENE 7: On-Chain Identity (30 sec)

**Show:** Terminal

**Say:**
> "Both agents hold verifiable on-chain identity as Metaplex Core NFTs on Solana, registered via the 8004 protocol."

**Action:** Run:
```bash
solana account HmMASnJ7WnUM6ZeasSus6G1cnZrmgbidh3GsgiEhtMfw --url devnet
```

**Point out:**
- The account is owned by the 8004 program
- The metadata URI points to our agent description
- The treasury agent has an operational wallet assigned

> "After each batch run, an ATOM reputation score is submitted on-chain — building a tamper-proof track record of funding decision quality. On submission day, we switch from devnet to mainnet."

---

## SCENE 8: Close (15 sec)

**Show:** Back to landing page at `localhost:5050/demo`

**Say:**
> "To recap — this is a fully autonomous grant allocation pipeline. Three AI agents evaluate proposals against a structured rubric, a treasury agent enforces hard budget constraints, every decision is explainable from the audit log alone, and both agents have verifiable on-chain identity on Solana. No human in the approval loop — but humans can override when needed."

> "Built for the Agentic Funding & Coordination track. Code is on GitHub."

**Action:** Point at the GitHub link on the page.

---

## Recording Tips

- **Resolution:** 1920x1080 or higher
- **Browser:** Use Chrome/Safari with dark mode to match the dashboard theme
- **Terminal:** Use a dark terminal theme, large font (14-16pt)
- **Tabs:** Pre-open all tabs before recording (demo page, dashboard, x402, terminal)
- **Pre-run:** Run one batch before recording so the dashboard already has data — then run another live during the demo to show the flow
- **Voiceover:** Speak at a steady pace. Pause briefly when pointing at specific UI elements
- **Cursor:** Use a large cursor or highlight tool so viewers can follow
