"""Treasury Agent — Phase 2.

Enforces budget constraints via HLOS wallet, makes approve/reject decisions,
writes ledger entries, and stores HLOS receipt hashes.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from .hlos import HLOSError, HLOSWallet
from .ledger import Ledger
from .schemas import (
    CoordinatorVerdict,
    Decision,
    EvaluationResult,
    LedgerEntry,
    Proposal,
)


def process_decision(
    evaluation: EvaluationResult,
    wallet: HLOSWallet,
    ledger: Ledger,
    original_requested_amount: float = 0.0,
    verdict: CoordinatorVerdict = None,
    max_hlos_retries: int = 3,
) -> LedgerEntry:
    """Make a funding decision based on the evaluation (or coordinator verdict) and wallet state.

    If a coordinator verdict is provided (Phase 3), it takes precedence over
    the raw evaluator output for scoring and recommendation.
    """
    balance_before = wallet.get_balance()
    trace_id = str(uuid.uuid4())[:8]

    # Use coordinator verdict if available, otherwise fall back to evaluator
    if verdict:
        score = verdict.final_score
        breakdown = verdict.final_breakdown
        dim_failures = verdict.dimension_failures
        amount_to_approve = verdict.final_recommended_amount
        base_rationale = verdict.synthesis
    else:
        score = evaluation.score_total
        breakdown = evaluation.score_breakdown
        dim_failures = evaluation.dimension_failures
        amount_to_approve = evaluation.recommended_amount
        base_rationale = evaluation.rationale

    # --- Decision logic ---
    if dim_failures:
        decision = Decision.REJECTED
        rationale = (
            f"Rejected: dimensions below minimum threshold: "
            f"{', '.join(dim_failures)}. {base_rationale}"
        )
        amount_to_approve = 0.0

    elif score < 50:
        decision = Decision.REJECTED
        rationale = (
            f"Rejected: total score {score}/100 below 50 threshold. "
            f"{base_rationale}"
        )
        amount_to_approve = 0.0

    elif amount_to_approve > balance_before:
        decision = Decision.REJECTED
        rationale = (
            f"Rejected: insufficient budget. Requested ${amount_to_approve:,.2f} "
            f"but only ${balance_before:,.2f} available. {base_rationale}"
        )
        amount_to_approve = 0.0

    else:
        decision = Decision.APPROVED
        rationale = (
            f"Approved: score {score}/100, "
            f"disbursing ${amount_to_approve:,.2f}. {base_rationale}"
        )

    # --- HLOS disbursement (if approved) ---
    receipt_hash = None
    balance_after = balance_before

    if decision == Decision.APPROVED and amount_to_approve > 0:
        last_error = None
        for attempt in range(max_hlos_retries):
            try:
                receipt = wallet.notarize(evaluation.proposal_id, amount_to_approve)
                receipt_hash = receipt.receipt_hash
                balance_after = wallet.get_balance()
                break
            except HLOSError as e:
                last_error = e
                if attempt == max_hlos_retries - 1:
                    # Escalate after all retries exhausted
                    decision = Decision.ESCALATED
                    rationale = (
                        f"Escalated: HLOS disbursement failed after "
                        f"{max_hlos_retries} attempts. Error: {last_error}. "
                        f"Original decision was APPROVED for "
                        f"${amount_to_approve:,.2f}."
                    )
                    amount_to_approve = 0.0

    # --- Write ledger entry (always, regardless of outcome) ---
    entry = LedgerEntry(
        proposal_id=evaluation.proposal_id,
        decision=decision,
        score_total=score,
        score_breakdown=breakdown,
        rationale=rationale,
        amount_requested=original_requested_amount or evaluation.recommended_amount,
        amount_approved=amount_to_approve,
        balance_before=balance_before,
        balance_after=balance_after,
        hlos_receipt_hash=receipt_hash,
        decided_at=datetime.utcnow(),
        agent_trace_id=trace_id,
        evaluator_score=evaluation.score_total,
        skeptic_score=verdict.final_score if verdict else None,
        coordinator_synthesis=verdict.synthesis if verdict else None,
        overrode_evaluator=verdict.overrode_evaluator if verdict else False,
        is_resubmission=verdict.is_resubmission if verdict else False,
    )
    ledger.append(entry)
    return entry
