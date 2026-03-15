"""Main entry point — batch proposal processing pipeline.

Phase 1+2+3: Evaluator + Skeptic + Coordinator panel, Treasury enforcement.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .coordinator import coordinate
from .evaluator import evaluate_proposal
from .hlos import HLOSWallet
from .ledger import Ledger
from .schemas import Proposal
from .skeptic import challenge_proposal
from .treasury import process_decision


def load_proposals(path: str) -> list[Proposal]:
    """Load proposals from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return [Proposal(**p) for p in data]


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def main() -> None:
    load_dotenv()

    # --- Config ---
    proposals_path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_proposals.json"
    ledger_path = "ledger.json"
    model = sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet-4-6"

    # Auto-detect evaluator mode
    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    use_mock = not has_api_key
    agent_mode = "mock (heuristic)" if use_mock else f"live ({model})"

    print_header("AGENTIC GRANT ALLOCATION SYSTEM")
    print("  3-Agent Panel: Evaluator + Skeptic + Coordinator")
    print("  HLOS / STAAMP Credential Isolation")

    # --- Initialize ---
    wallet = HLOSWallet.connect()
    ledger = Ledger(path=ledger_path)

    # Initialize STAAMP client with wallet for credential isolation
    if not use_mock:
        from .staamp import get_anthropic_client
        get_anthropic_client(wallet)

    print(f"\n  Proposals:  {proposals_path}")
    print(f"  Agents:     {agent_mode}")
    print(f"  HLOS:       {wallet.mode_label}")
    print(f"  Wallet:     ${wallet.get_balance():,.2f}")
    print(f"  Ledger:     {ledger_path}")

    if use_mock:
        print("\n  [!] No ANTHROPIC_API_KEY found — using mock agents.")
        print("      Set ANTHROPIC_API_KEY in .env to use Claude.\n")

    proposals = load_proposals(proposals_path)
    print(f"  Batch size: {len(proposals)} proposals\n")

    # --- Process batch ---
    results = []
    overrides = 0

    for i, proposal in enumerate(proposals, 1):
        print(f"\n--- [{i}/{len(proposals)}] {proposal.id}: {proposal.title} ---")
        print(f"    Requested: ${proposal.requested_amount:,.2f}")

        # Agent 1: Evaluator
        print("    [Evaluator]...", end=" ", flush=True)
        evaluation = evaluate_proposal(proposal, use_mock=use_mock, model=model)
        print(f"Score: {evaluation.score_total}/100")

        # Agent 2: Skeptic
        print("    [Skeptic]...", end=" ", flush=True)
        challenge = challenge_proposal(proposal, evaluation, use_mock=use_mock, model=model)
        agree_str = "AGREES" if challenge.agrees_with_evaluator else "DISAGREES"
        print(f"Score: {challenge.adjusted_score}/100 ({agree_str})")
        if challenge.key_concerns:
            print(f"    Concerns: {'; '.join(challenge.key_concerns[:2])}")

        # Agent 3: Coordinator
        print("    [Coordinator]...", end=" ", flush=True)
        verdict = coordinate(proposal, evaluation, challenge, ledger, use_mock=use_mock, model=model)
        override_str = " ** OVERRIDE **" if verdict.overrode_evaluator else ""
        resub_str = " [RESUBMISSION]" if verdict.is_resubmission else ""
        print(f"Final: {verdict.final_score}/100{override_str}{resub_str}")
        if verdict.overrode_evaluator:
            overrides += 1

        # Show final breakdown
        bd = verdict.final_breakdown
        print(f"    Final breakdown: team={bd.team} impact={bd.impact} "
              f"budget={bd.budget} alignment={bd.alignment} risk={bd.risk}")
        if verdict.dimension_failures:
            print(f"    FAILED dimensions: {', '.join(verdict.dimension_failures)}")
        print(f"    Recommended: ${verdict.final_recommended_amount:,.2f}")
        print(f"    Synthesis: {verdict.synthesis[:120]}...")

        # Treasury decision (uses coordinator verdict)
        print("    [Treasury]...", end=" ", flush=True)
        entry = process_decision(
            evaluation, wallet, ledger,
            original_requested_amount=proposal.requested_amount,
            verdict=verdict,
        )
        print(f"{entry.decision.value}")
        print(f"    Amount approved: ${entry.amount_approved:,.2f}")
        print(f"    Balance: ${entry.balance_before:,.2f} -> ${entry.balance_after:,.2f}")
        if entry.hlos_receipt_hash:
            print(f"    Receipt: {entry.hlos_receipt_hash}")

        results.append(entry)

    # --- Batch summary ---
    print_header("BATCH SUMMARY")
    approved = [r for r in results if r.decision.value == "APPROVED"]
    rejected = [r for r in results if r.decision.value == "REJECTED"]
    escalated = [r for r in results if r.decision.value == "ESCALATED"]

    total_disbursed = sum(r.amount_approved for r in approved)

    print(f"\n  Total proposals:  {len(results)}")
    print(f"  Approved:         {len(approved)}")
    print(f"  Rejected:         {len(rejected)}")
    print(f"  Escalated:        {len(escalated)}")
    print(f"  Overrides:        {overrides}")
    print(f"  Total disbursed:  ${total_disbursed:,.2f}")
    print(f"  Final balance:    ${wallet.get_balance():,.2f}")
    print(f"\n  Ledger written to: {ledger_path}")

    if approved:
        print("\n  Approved proposals:")
        for r in approved:
            print(f"    - {r.proposal_id}: ${r.amount_approved:,.2f} [{r.hlos_receipt_hash}]")

    # --- Solana ATOM feedback ---
    _submit_onchain_feedback(results, len(proposals))

    print()


def _submit_onchain_feedback(results: list, total_proposals: int) -> None:
    """Submit batch quality score to Solana via ATOM reputation feedback."""
    try:
        approved = sum(1 for r in results if r.decision.value == "APPROVED")
        avg_score = sum(r.score_total for r in results) / max(len(results), 1)
        # Quality score: weighted average of proposal scores (0-100)
        quality = round(avg_score, 1)

        import subprocess
        import shutil

        npx = shutil.which("npx")
        if not npx:
            return

        # Check if solana/.env has TREASURY_AGENT_ASSET configured
        solana_env = Path("solana/.env")
        if not solana_env.exists():
            return
        env_content = solana_env.read_text()
        if "TREASURY_AGENT_ASSET=''" in env_content or "TREASURY_AGENT_ASSET=" not in env_content:
            return

        print(f"\n  [Solana] Submitting ATOM feedback (quality: {quality})...", end=" ", flush=True)
        result = subprocess.run(
            [npx, "ts-node", "solana/feedback.ts", str(quality)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print("done.")
            for line in result.stdout.strip().split("\n"):
                print(f"    {line}")
        else:
            print("skipped (not configured).")
    except Exception:
        # Solana feedback is best-effort, never block the batch
        pass


if __name__ == "__main__":
    main()
