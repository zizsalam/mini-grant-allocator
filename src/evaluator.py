"""Evaluator Agent — Phase 1.

Two modes:
- Live mode: Claude scores proposals via Anthropic API (requires ANTHROPIC_API_KEY)
- Mock mode: rule-based heuristic scorer for local dev without an API key
"""

from __future__ import annotations

import json
import re
from typing import Optional

from .schemas import (
    DIMENSION_MINIMUMS,
    EvaluationResult,
    Proposal,
    ScoreBreakdown,
)

SYSTEM_PROMPT = """\
You are a grant evaluator agent. Your job is to score grant proposals against a \
structured rubric and return a JSON evaluation.

## Scoring Rubric (each dimension: 0–20 points, total 0–100)

1. **Team credibility** (min 10 to pass): Track record, relevant expertise, \
prior delivery evidence.
2. **Impact potential** (min 12 to pass): Scale of addressable problem, \
measurable outcome hypothesis.
3. **Budget realism** (min 10 to pass): Requested amount vs. scope; cost \
breakdown quality.
4. **Goal alignment** (min 12 to pass): Match with stated funding priorities \
(clean water, health, education, open-source tooling).
5. **Execution risk** (min 8 to pass): Technical, market, or dependency risks \
identified and mitigated.

## Decision Thresholds
- Score >= 70: Recommend FULL requested amount.
- Score 50–69: Recommend 50–75% of requested amount (scale linearly).
- Score < 50: Recommend $0 (reject).
- ANY dimension below its minimum: Auto-reject regardless of total score.

## Output Format
Return ONLY valid JSON (no markdown fences, no extra text) with this exact structure:
{
  "proposal_id": "<id>",
  "score_total": <0-100>,
  "score_breakdown": {
    "team": <0-20>,
    "impact": <0-20>,
    "budget": <0-20>,
    "alignment": <0-20>,
    "risk": <0-20>
  },
  "recommended_amount": <number>,
  "rationale": "<2-3 sentence explanation>",
  "flags": ["<optional flag strings>"],
  "dimension_failures": ["<dimensions below minimum, if any>"]
}

Be rigorous but fair. Vague proposals with no evidence should score low. \
Strong proposals with clear track records and budgets should score high.
"""


# ---------------------------------------------------------------------------
# Heuristic signals used by the mock evaluator
# ---------------------------------------------------------------------------
_TEAM_SIGNALS = [
    "years", "experience", "PhD", "Dr.", "professor", "published", "deployed",
    "prior", "track record", "ex-Google", "ex-", "founded", "built", "served",
    "led", "senior", "engineer", "scientist", "clinics", "peer-reviewed",
]
_IMPACT_SIGNALS = [
    "people", "communities", "patients", "users", "scale", "reduce",
    "improve", "measurable", "outcome", "million", "thousand", "500,000",
    "nationwide", "global", "country", "region", "ministry", "impact",
    "address", "benefit", "serve", "expand", "reach",
]
_BUDGET_SIGNALS = [
    "breakdown", "$", "budget:", "materials", "training", "development",
    "lab", "hardware", "onboarding", "data plans", "documentation",
]
_ALIGNMENT_SIGNALS = [
    "water", "health", "education", "open-source", "maternal", "clean",
    "sensor", "rural", "community", "clinic", "monitoring", "filtration",
]
_RISK_SIGNALS = [
    "pilot", "trial", "letter of intent", "partner", "tested", "proven",
    "mitigation", "contingency", "patent", "prototype", "deployed",
    "verified", "track record", "established", "working", "existing",
]


def _count_signals(text: str, signals: list[str]) -> int:
    text_lower = text.lower()
    return sum(1 for s in signals if s.lower() in text_lower)


def _clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


def _compute_recommended_amount(score: int, requested: float) -> float:
    if score >= 70:
        return requested
    elif score >= 50:
        # Linear scale: 50->50%, 69->75%
        pct = 0.50 + (score - 50) * (0.25 / 19)
        return round(requested * pct, 2)
    return 0.0


def _apply_minimums(result: EvaluationResult) -> EvaluationResult:
    """Check dimension minimums and enforce auto-reject."""
    breakdown = result.score_breakdown
    failures = []
    for dim, min_score in DIMENSION_MINIMUMS.items():
        if getattr(breakdown, dim) < min_score:
            failures.append(dim)
    result.dimension_failures = failures
    if failures and result.recommended_amount > 0:
        result.recommended_amount = 0
        result.flags.append("auto-reject: dimension minimum not met")
    return result


def evaluate_proposal_mock(proposal: Proposal) -> EvaluationResult:
    """Rule-based heuristic evaluator for local dev (no API key needed)."""
    text = f"{proposal.title} {proposal.text}"
    word_count = len(text.split())

    # Score each dimension based on signal presence + text length heuristics
    # Longer, more detailed proposals get a length bonus (up to +4)
    length_bonus = _clamp(word_count // 40, 0, 4)

    team = _clamp(5 + _count_signals(text, _TEAM_SIGNALS) * 2 + length_bonus, 0, 20)
    impact = _clamp(5 + _count_signals(text, _IMPACT_SIGNALS) * 2 + length_bonus, 0, 20)
    budget = _clamp(5 + _count_signals(text, _BUDGET_SIGNALS) * 2 + length_bonus, 0, 20)
    alignment = _clamp(5 + _count_signals(text, _ALIGNMENT_SIGNALS) * 2 + length_bonus, 0, 20)
    risk = _clamp(5 + _count_signals(text, _RISK_SIGNALS) * 2 + length_bonus, 0, 20)

    # Penalize very short proposals (< 50 words = low effort)
    if word_count < 50:
        team = min(team, 6)
        impact = min(impact, 6)
        budget = min(budget, 6)

    total = team + impact + budget + alignment + risk
    recommended = _compute_recommended_amount(total, proposal.requested_amount)

    # Build rationale
    if total >= 70:
        rationale = (
            f"Strong proposal with clear evidence across dimensions. "
            f"Word count ({word_count}) indicates substantive detail."
        )
    elif total >= 50:
        rationale = (
            f"Moderate proposal with some strengths but gaps in evidence. "
            f"Partial funding recommended."
        )
    else:
        rationale = (
            f"Weak proposal lacking sufficient evidence of team capability, "
            f"impact potential, or budget realism. Rejection recommended."
        )

    result = EvaluationResult(
        proposal_id=proposal.id,
        score_total=total,
        score_breakdown=ScoreBreakdown(
            team=team, impact=impact, budget=budget,
            alignment=alignment, risk=risk,
        ),
        recommended_amount=recommended,
        rationale=rationale,
        flags=["mock-evaluator"],
    )
    return _apply_minimums(result)


def evaluate_proposal_live(
    proposal: Proposal,
    model: str = "claude-sonnet-4-6",
    max_retries: int = 2,
) -> EvaluationResult:
    """Score a single proposal using Claude via STAAMP credential isolation.

    Retries on malformed JSON output up to max_retries times.
    """
    from .staamp import get_anthropic_client

    client = get_anthropic_client()
    user_message = (
        f"Proposal ID: {proposal.id}\n"
        f"Title: {proposal.title}\n"
        f"Requested Amount: ${proposal.requested_amount:,.2f}\n"
        f"Applicant: {proposal.applicant_id}\n"
        f"Submitted: {proposal.submitted_at.isoformat()}\n\n"
        f"--- PROPOSAL TEXT ---\n{proposal.text}\n--- END ---"
    )

    last_error = None
    for attempt in range(max_retries + 1):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            data = json.loads(raw)
            result = EvaluationResult(**data)
            return _apply_minimums(result)
        except (json.JSONDecodeError, Exception) as e:
            last_error = e
            continue

    raise RuntimeError(
        f"Evaluator failed to produce valid JSON after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


def evaluate_proposal(
    proposal: Proposal,
    use_mock: bool = True,
    model: str = "claude-sonnet-4-6",
) -> EvaluationResult:
    """Score a proposal. Uses mock evaluator by default; set use_mock=False for Claude."""
    if use_mock:
        return evaluate_proposal_mock(proposal)
    return evaluate_proposal_live(proposal, model=model)
