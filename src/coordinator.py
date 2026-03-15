"""Coordinator Agent — Phase 3.

Resolves disagreements between evaluator and skeptic agents.
Detects resubmissions and applies prior decision context.
Issues final verdict with synthesis reasoning.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from .ledger import Ledger
from .schemas import (
    DIMENSION_MINIMUMS,
    CoordinatorVerdict,
    EvaluationResult,
    Proposal,
    ScoreBreakdown,
    SkepticChallenge,
)

COORDINATOR_SYSTEM_PROMPT = """\
You are the coordinator agent in a grant evaluation panel. You receive scores from \
two agents — an evaluator and a skeptic — and must issue the final verdict.

Your role:
1. Weigh both perspectives fairly
2. Resolve specific disagreements with explicit reasoning
3. If this is a resubmission, factor in the prior decision
4. Issue a final score and funding recommendation

## Decision Thresholds
- Score >= 70: Recommend FULL requested amount
- Score 50–69: Recommend 50–75% of requested amount
- Score < 50: Recommend $0 (reject)
- ANY dimension below minimum: Auto-reject (team>=10, impact>=12, budget>=10, alignment>=12, risk>=8)

## Resubmission Policy
If a proposal was previously rejected, the bar is higher:
- The resubmission must address the prior rejection reasons
- If no meaningful changes, apply a -5 penalty to total score

## Output Format
Return ONLY valid JSON:
{
  "proposal_id": "<id>",
  "final_score": <0-100>,
  "final_breakdown": {
    "team": <0-20>, "impact": <0-20>, "budget": <0-20>,
    "alignment": <0-20>, "risk": <0-20>
  },
  "final_recommended_amount": <number>,
  "synthesis": "<3-4 sentences: how you weighed both perspectives, why you agree/disagree>",
  "overrode_evaluator": <true/false>,
  "dimension_failures": ["<dimensions below minimum, if any>"],
  "is_resubmission": <true/false>,
  "prior_decision": "<APPROVED|REJECTED|null>"
}
"""


def _compute_recommended(score: int, requested: float) -> float:
    if score >= 70:
        return requested
    elif score >= 50:
        pct = 0.50 + (score - 50) * (0.25 / 19)
        return round(requested * pct, 2)
    return 0.0


def _check_dimension_failures(bd: ScoreBreakdown) -> list[str]:
    failures = []
    for dim, min_score in DIMENSION_MINIMUMS.items():
        if getattr(bd, dim) < min_score:
            failures.append(dim)
    return failures


def check_resubmission(proposal_id: str, applicant_id: str, ledger: Ledger) -> Optional[dict]:
    """Check if this proposal or applicant has a prior decision in the ledger."""
    entries = ledger.read_all()
    # Check by proposal_id prefix (e.g., PROP-001 resubmitted as PROP-001-R2)
    base_id = proposal_id.rsplit("-R", 1)[0] if "-R" in proposal_id else proposal_id
    for entry in reversed(entries):
        entry_base = entry["proposal_id"].rsplit("-R", 1)[0] if "-R" in entry["proposal_id"] else entry["proposal_id"]
        if entry_base == base_id:
            return entry
    return None


def coordinate_mock(
    proposal: Proposal,
    evaluation: EvaluationResult,
    challenge: SkepticChallenge,
    prior_decision: Optional[dict] = None,
) -> CoordinatorVerdict:
    """Mock coordinator: averages scores, favors skeptic on disagreements."""
    eval_bd = evaluation.score_breakdown
    skep_bd = challenge.adjusted_breakdown
    is_resub = prior_decision is not None

    # Weighted average: 55% evaluator, 45% skeptic (slight evaluator preference)
    # But if skeptic strongly disagrees (>10 point gap), weight skeptic more
    gap = abs(evaluation.score_total - challenge.adjusted_score)
    if gap > 10:
        eval_w, skep_w = 0.45, 0.55  # Favor skeptic on big disagreements
    else:
        eval_w, skep_w = 0.55, 0.45

    team = round(eval_bd.team * eval_w + skep_bd.team * skep_w)
    impact = round(eval_bd.impact * eval_w + skep_bd.impact * skep_w)
    budget = round(eval_bd.budget * eval_w + skep_bd.budget * skep_w)
    alignment = round(eval_bd.alignment * eval_w + skep_bd.alignment * skep_w)
    risk = round(eval_bd.risk * eval_w + skep_bd.risk * skep_w)

    # Clamp to valid range
    team = max(0, min(20, team))
    impact = max(0, min(20, impact))
    budget = max(0, min(20, budget))
    alignment = max(0, min(20, alignment))
    risk = max(0, min(20, risk))

    total = team + impact + budget + alignment + risk

    # Resubmission penalty
    if is_resub and prior_decision and prior_decision.get("decision") == "REJECTED":
        total = max(0, total - 5)

    final_bd = ScoreBreakdown(
        team=team, impact=impact, budget=budget,
        alignment=alignment, risk=risk,
    )
    failures = _check_dimension_failures(final_bd)

    recommended = _compute_recommended(total, proposal.requested_amount)
    if failures:
        recommended = 0.0

    overrode = abs(total - evaluation.score_total) >= 8

    # Build synthesis
    if challenge.agrees_with_evaluator:
        synthesis = (
            f"Both evaluator ({evaluation.score_total}) and skeptic "
            f"({challenge.adjusted_score}) largely agree. "
            f"Final score: {total}/100."
        )
    elif overrode:
        synthesis = (
            f"Evaluator scored {evaluation.score_total}, skeptic scored "
            f"{challenge.adjusted_score}. Significant disagreement detected. "
            f"After weighing concerns ({'; '.join(challenge.key_concerns[:2])}), "
            f"coordinator overrode evaluator. Final score: {total}/100."
        )
    else:
        synthesis = (
            f"Evaluator scored {evaluation.score_total}, skeptic scored "
            f"{challenge.adjusted_score}. Minor disagreement resolved by "
            f"averaging. Final score: {total}/100."
        )

    if is_resub:
        synthesis += (
            f" This is a resubmission (prior decision: "
            f"{prior_decision.get('decision', 'UNKNOWN')}). "
            f"A -5 penalty was applied."
        )

    return CoordinatorVerdict(
        proposal_id=proposal.id,
        final_score=total,
        final_breakdown=final_bd,
        final_recommended_amount=recommended,
        synthesis=synthesis,
        overrode_evaluator=overrode,
        dimension_failures=failures,
        is_resubmission=is_resub,
        prior_decision=prior_decision.get("decision") if prior_decision else None,
    )


def coordinate_live(
    proposal: Proposal,
    evaluation: EvaluationResult,
    challenge: SkepticChallenge,
    prior_decision: Optional[dict] = None,
    model: str = "claude-sonnet-4-6",
    max_retries: int = 2,
) -> CoordinatorVerdict:
    """Coordinator agent powered by Claude via STAAMP credential isolation."""
    from .staamp import get_anthropic_client

    client = get_anthropic_client()
    eval_bd = evaluation.score_breakdown
    skep_bd = challenge.adjusted_breakdown

    user_message = (
        f"## Proposal\n"
        f"ID: {proposal.id} | Title: {proposal.title}\n"
        f"Requested: ${proposal.requested_amount:,.2f}\n\n"
        f"--- PROPOSAL TEXT ---\n{proposal.text}\n--- END ---\n\n"
        f"## Evaluator Assessment\n"
        f"Score: {evaluation.score_total}/100\n"
        f"Breakdown: team={eval_bd.team} impact={eval_bd.impact} "
        f"budget={eval_bd.budget} alignment={eval_bd.alignment} risk={eval_bd.risk}\n"
        f"Rationale: {evaluation.rationale}\n\n"
        f"## Skeptic Challenge\n"
        f"Adjusted Score: {challenge.adjusted_score}/100\n"
        f"Breakdown: team={skep_bd.team} impact={skep_bd.impact} "
        f"budget={skep_bd.budget} alignment={skep_bd.alignment} risk={skep_bd.risk}\n"
        f"Agrees with evaluator: {challenge.agrees_with_evaluator}\n"
        f"Challenge: {challenge.challenge_text}\n"
        f"Key concerns: {', '.join(challenge.key_concerns)}\n"
    )

    if prior_decision:
        user_message += (
            f"\n## Resubmission Context\n"
            f"This proposal was previously {prior_decision.get('decision', 'UNKNOWN')}.\n"
            f"Prior score: {prior_decision.get('score_total', 'N/A')}/100\n"
            f"Prior rationale: {prior_decision.get('rationale', 'N/A')}\n"
        )

    last_error = None
    for attempt in range(max_retries + 1):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=COORDINATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            data = json.loads(raw)
            return CoordinatorVerdict(**data)
        except (json.JSONDecodeError, Exception) as e:
            last_error = e
            continue

    raise RuntimeError(
        f"Coordinator failed after {max_retries + 1} attempts. Last error: {last_error}"
    )


def coordinate(
    proposal: Proposal,
    evaluation: EvaluationResult,
    challenge: SkepticChallenge,
    ledger: Ledger,
    use_mock: bool = True,
    model: str = "claude-sonnet-4-6",
) -> CoordinatorVerdict:
    """Run coordinator to produce final verdict."""
    prior = check_resubmission(proposal.id, proposal.applicant_id, ledger)
    if use_mock:
        return coordinate_mock(proposal, evaluation, challenge, prior)
    return coordinate_live(proposal, evaluation, challenge, prior, model=model)
