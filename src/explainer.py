"""Explainability Engine — Phase 4.

Generates plain-language explanations of any decision from the ledger alone,
without re-running any agents.
"""

from __future__ import annotations

from .schemas import DIMENSION_MINIMUMS


def explain_decision(entry: dict) -> str:
    """Generate a full plain-language explanation from a single ledger entry."""
    pid = entry["proposal_id"]
    decision = entry["decision"]
    score = entry["score_total"]
    bd = entry["score_breakdown"]
    amount_req = entry["amount_requested"]
    amount_app = entry["amount_approved"]
    bal_before = entry["balance_before"]
    bal_after = entry["balance_after"]
    rationale = entry.get("rationale", "")
    synthesis = entry.get("coordinator_synthesis", "")
    eval_score = entry.get("evaluator_score")
    skep_score = entry.get("skeptic_score")
    overrode = entry.get("overrode_evaluator", False)
    is_resub = entry.get("is_resubmission", False)
    receipt = entry.get("hlos_receipt_hash")
    override_by = entry.get("human_override_by")
    override_reason = entry.get("human_override_reason")

    lines = []
    lines.append(f"DECISION EXPLANATION: {pid}")
    lines.append(f"{'='*50}")

    # 1. Outcome
    lines.append(f"\nOutcome: {decision}")
    if override_by:
        lines.append(
            f"  ** This decision was manually overridden by {override_by}. **"
        )
        lines.append(f"  Override reason: {override_reason}")
    lines.append(f"Amount requested: ${amount_req:,.2f}")
    lines.append(f"Amount approved:  ${amount_app:,.2f}")

    # 2. Agent panel scores
    lines.append(f"\nAgent Panel Scores:")
    if eval_score is not None:
        lines.append(f"  Evaluator:   {eval_score}/100")
    if skep_score is not None:
        lines.append(f"  Skeptic:     {skep_score}/100")
    lines.append(f"  Final score: {score}/100")
    if overrode:
        lines.append(
            f"  ** Coordinator overrode the evaluator's original assessment. **"
        )

    # 3. Dimension breakdown
    lines.append(f"\nDimension Breakdown (each 0-20, minimum to pass shown):")
    dims = [
        ("Team credibility", "team"),
        ("Impact potential", "impact"),
        ("Budget realism", "budget"),
        ("Goal alignment", "alignment"),
        ("Execution risk", "risk"),
    ]
    failed_dims = []
    for label, key in dims:
        val = bd[key]
        minimum = DIMENSION_MINIMUMS[key]
        status = "PASS" if val >= minimum else "FAIL"
        if status == "FAIL":
            failed_dims.append(label)
        lines.append(f"  {label:20s}: {val:2d}/20 (min {minimum:2d}) [{status}]")

    # 4. Decision reasoning
    lines.append(f"\nDecision Logic:")
    if failed_dims:
        lines.append(
            f"  - Auto-reject triggered: {', '.join(failed_dims)} "
            f"below minimum threshold"
        )
    elif score < 50:
        lines.append(f"  - Total score {score} is below the 50-point threshold")
        lines.append(f"  - Result: REJECTED")
    elif score < 70:
        pct = 50 + (score - 50) * (25 / 19)
        lines.append(
            f"  - Score {score} is in partial funding range (50-69)"
        )
        lines.append(f"  - Funding at ~{pct:.0f}% of requested amount")
    else:
        lines.append(f"  - Score {score} meets full funding threshold (>=70)")

    if amount_app > 0 and amount_app > bal_before:
        lines.append(
            f"  - Insufficient budget: needed ${amount_app:,.2f} "
            f"but only ${bal_before:,.2f} available"
        )

    # 5. Coordinator synthesis
    if synthesis:
        lines.append(f"\nCoordinator Synthesis:")
        lines.append(f"  {synthesis}")

    # 6. Budget impact
    lines.append(f"\nBudget Impact:")
    lines.append(f"  Balance before: ${bal_before:,.2f}")
    lines.append(f"  Balance after:  ${bal_after:,.2f}")
    if receipt:
        lines.append(f"  HLOS receipt:   {receipt}")

    # 7. Resubmission context
    if is_resub:
        lines.append(f"\nResubmission:")
        lines.append(f"  This proposal was previously submitted and re-evaluated.")
        lines.append(f"  A scoring penalty was applied per resubmission policy.")

    lines.append(f"\nTimestamp: {entry.get('decided_at', 'N/A')}")
    lines.append(f"Trace ID:  {entry.get('agent_trace_id', 'N/A')}")

    return "\n".join(lines)


def explain_batch(entries: list[dict], report: dict = None) -> str:
    """Generate a plain-language batch summary from ledger entries + optional report."""
    approved = [e for e in entries if e["decision"] == "APPROVED"]
    rejected = [e for e in entries if e["decision"] == "REJECTED"]
    escalated = [e for e in entries if e["decision"] == "ESCALATED"]
    overrides_count = sum(1 for e in entries if e.get("overrode_evaluator"))
    human_overrides = sum(1 for e in entries if e.get("human_override_by"))
    total_disbursed = sum(e["amount_approved"] for e in approved)

    lines = []
    lines.append("BATCH SUMMARY REPORT")
    lines.append("=" * 50)
    lines.append(f"\nProposals processed: {len(entries)}")
    lines.append(f"Approved:            {len(approved)}")
    lines.append(f"Rejected:            {len(rejected)}")
    lines.append(f"Escalated:           {len(escalated)}")
    lines.append(f"Coordinator overrides: {overrides_count}")
    lines.append(f"Human overrides:     {human_overrides}")
    lines.append(f"\nTotal disbursed:     ${total_disbursed:,.2f}")
    if entries:
        lines.append(f"Final balance:       ${entries[-1]['balance_after']:,.2f}")

    if report:
        totals = report.get("totals", {})
        lines.append(f"\nLLM Usage:")
        lines.append(f"  Agent calls:       {totals.get('agent_calls', 0)}")
        lines.append(f"  Input tokens:      {totals.get('input_tokens', 0):,}")
        lines.append(f"  Output tokens:     {totals.get('output_tokens', 0):,}")
        lines.append(f"  Total tokens:      {totals.get('total_tokens', 0):,}")
        lines.append(f"  Estimated cost:    ${totals.get('llm_cost', 0):.4f}")
        lines.append(f"  Total latency:     {totals.get('total_latency_ms', 0):,.0f}ms")

    if approved:
        lines.append(f"\nApproved Proposals:")
        for e in approved:
            lines.append(
                f"  {e['proposal_id']}: ${e['amount_approved']:,.2f} "
                f"(score {e['score_total']}/100) "
                f"[{e.get('hlos_receipt_hash', 'no-receipt')}]"
            )

    if rejected:
        lines.append(f"\nRejected Proposals:")
        for e in rejected:
            lines.append(
                f"  {e['proposal_id']}: score {e['score_total']}/100"
            )

    return "\n".join(lines)
