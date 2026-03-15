"""Skeptic Agent — Phase 3.

Challenges the evaluator's scores by looking for weaknesses,
overstatements, and risks the evaluator may have missed.
"""

from __future__ import annotations

import json
import re

from .schemas import (
    DIMENSION_MINIMUMS,
    EvaluationResult,
    Proposal,
    ScoreBreakdown,
    SkepticChallenge,
)

SKEPTIC_SYSTEM_PROMPT = """\
You are a skeptic agent in a grant evaluation panel. Your role is to challenge \
the evaluator's assessment by looking for weaknesses, overstatements, missing \
evidence, and risks that may have been overlooked.

You will receive:
1. The original proposal text
2. The evaluator's score and rationale

Your job is NOT to be contrarian for its own sake. You should:
- Identify specific claims in the proposal that lack evidence
- Flag overgenerous scores where the proposal doesn't warrant them
- Note risks or dependencies the evaluator may have underweighted
- Acknowledge where the evaluator got it right

## Scoring Rubric (same as evaluator, each 0-20, total 0-100)
1. Team credibility (min 10): Track record, expertise, delivery evidence
2. Impact potential (min 12): Scale of problem, measurable outcomes
3. Budget realism (min 10): Amount vs. scope, cost breakdown quality
4. Goal alignment (min 12): Match with funding priorities (water, health, education, open-source)
5. Execution risk (min 8): Risks identified and mitigated

## Output Format
Return ONLY valid JSON:
{
  "proposal_id": "<id>",
  "challenge_text": "<2-3 sentences explaining your challenge>",
  "adjusted_score": <0-100>,
  "adjusted_breakdown": {
    "team": <0-20>, "impact": <0-20>, "budget": <0-20>,
    "alignment": <0-20>, "risk": <0-20>
  },
  "agrees_with_evaluator": <true/false>,
  "key_concerns": ["<concern 1>", "<concern 2>"]
}

If you mostly agree, say so and keep scores within 5 points of the evaluator. \
If you disagree, explain why clearly and adjust scores accordingly.
"""


def challenge_proposal_mock(
    proposal: Proposal,
    evaluation: EvaluationResult,
) -> SkepticChallenge:
    """Mock skeptic: applies systematic downward pressure on evaluator scores."""
    bd = evaluation.score_breakdown
    text = f"{proposal.title} {proposal.text}".lower()
    word_count = len(text.split())

    # Skeptic applies penalties for common weaknesses
    penalties = {
        "team": 0, "impact": 0, "budget": 0, "alignment": 0, "risk": 0,
    }

    # Short proposals get extra skepticism
    if word_count < 80:
        penalties["team"] += 3
        penalties["impact"] += 2

    # No specific numbers = skeptic doubts impact claims
    if not any(c.isdigit() for c in proposal.text):
        penalties["impact"] += 4

    # No cost breakdown = budget skepticism
    if "$" not in proposal.text and "budget" not in text:
        penalties["budget"] += 4

    # Buzzword penalty (blockchain, token, NFT, revolutionize, disrupt)
    buzzwords = ["blockchain", "token", "nft", "revolutionize", "disrupt", "web3"]
    buzz_count = sum(1 for b in buzzwords if b in text)
    if buzz_count > 0:
        penalties["alignment"] += buzz_count * 2
        penalties["risk"] += buzz_count * 2

    # Apply penalties
    adj_team = max(0, bd.team - penalties["team"])
    adj_impact = max(0, bd.impact - penalties["impact"])
    adj_budget = max(0, bd.budget - penalties["budget"])
    adj_alignment = max(0, bd.alignment - penalties["alignment"])
    adj_risk = max(0, bd.risk - penalties["risk"])
    adj_total = adj_team + adj_impact + adj_budget + adj_alignment + adj_risk

    total_penalty = sum(penalties.values())
    agrees = total_penalty <= 5

    concerns = []
    if penalties["team"] > 0:
        concerns.append("Team credentials lack specific evidence")
    if penalties["impact"] > 0:
        concerns.append("Impact claims not supported by concrete metrics")
    if penalties["budget"] > 0:
        concerns.append("Budget breakdown insufficient or missing")
    if buzz_count > 0:
        concerns.append(f"Proposal relies on {buzz_count} buzzword(s) without substance")

    if agrees:
        challenge_text = (
            f"Largely agree with evaluator's assessment (score {evaluation.score_total}). "
            f"Minor concerns noted but overall evaluation is fair."
        )
    else:
        challenge_text = (
            f"Disagree with evaluator's score of {evaluation.score_total}. "
            f"Adjusted to {adj_total} due to: {', '.join(concerns[:2])}."
        )

    return SkepticChallenge(
        proposal_id=proposal.id,
        challenge_text=challenge_text,
        adjusted_score=adj_total,
        adjusted_breakdown=ScoreBreakdown(
            team=adj_team, impact=adj_impact, budget=adj_budget,
            alignment=adj_alignment, risk=adj_risk,
        ),
        agrees_with_evaluator=agrees,
        key_concerns=concerns,
    )


def challenge_proposal_live(
    proposal: Proposal,
    evaluation: EvaluationResult,
    model: str = "claude-sonnet-4-6",
    max_retries: int = 2,
) -> SkepticChallenge:
    """Skeptic agent powered by Claude via STAAMP credential isolation."""
    from .staamp import get_anthropic_client

    client = get_anthropic_client()
    bd = evaluation.score_breakdown

    user_message = (
        f"## Original Proposal\n"
        f"Proposal ID: {proposal.id}\n"
        f"Title: {proposal.title}\n"
        f"Requested Amount: ${proposal.requested_amount:,.2f}\n\n"
        f"--- PROPOSAL TEXT ---\n{proposal.text}\n--- END ---\n\n"
        f"## Evaluator's Assessment\n"
        f"Total Score: {evaluation.score_total}/100\n"
        f"Breakdown: team={bd.team} impact={bd.impact} budget={bd.budget} "
        f"alignment={bd.alignment} risk={bd.risk}\n"
        f"Rationale: {evaluation.rationale}\n"
        f"Recommended Amount: ${evaluation.recommended_amount:,.2f}"
    )

    last_error = None
    for attempt in range(max_retries + 1):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SKEPTIC_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            data = json.loads(raw)
            return SkepticChallenge(**data)
        except (json.JSONDecodeError, Exception) as e:
            last_error = e
            continue

    raise RuntimeError(
        f"Skeptic failed to produce valid JSON after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


def challenge_proposal(
    proposal: Proposal,
    evaluation: EvaluationResult,
    use_mock: bool = True,
    model: str = "claude-sonnet-4-6",
) -> SkepticChallenge:
    """Challenge a proposal evaluation. Uses mock by default."""
    if use_mock:
        return challenge_proposal_mock(proposal, evaluation)
    return challenge_proposal_live(proposal, evaluation, model=model)
