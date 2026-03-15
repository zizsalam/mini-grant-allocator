"""Data models for the grant allocation system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Proposal(BaseModel):
    id: str
    title: str
    text: str
    requested_amount: float
    applicant_id: str
    submitted_at: datetime


class ScoreBreakdown(BaseModel):
    team: int = Field(ge=0, le=20, description="Team credibility score")
    impact: int = Field(ge=0, le=20, description="Impact potential score")
    budget: int = Field(ge=0, le=20, description="Budget realism score")
    alignment: int = Field(ge=0, le=20, description="Goal alignment score")
    risk: int = Field(ge=0, le=20, description="Execution risk score")


# Minimum passing scores per dimension (from PRD rubric)
DIMENSION_MINIMUMS = {
    "team": 10,
    "impact": 12,
    "budget": 10,
    "alignment": 12,
    "risk": 8,
}


class EvaluationResult(BaseModel):
    proposal_id: str
    score_total: int = Field(ge=0, le=100)
    score_breakdown: ScoreBreakdown
    recommended_amount: float
    rationale: str
    flags: list[str] = Field(default_factory=list)
    dimension_failures: list[str] = Field(
        default_factory=list,
        description="Dimensions that fell below minimum threshold",
    )


class Decision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class SkepticChallenge(BaseModel):
    proposal_id: str
    challenge_text: str
    adjusted_score: int = Field(ge=0, le=100)
    adjusted_breakdown: ScoreBreakdown
    agrees_with_evaluator: bool
    key_concerns: list[str] = Field(default_factory=list)


class CoordinatorVerdict(BaseModel):
    proposal_id: str
    final_score: int = Field(ge=0, le=100)
    final_breakdown: ScoreBreakdown
    final_recommended_amount: float
    synthesis: str
    overrode_evaluator: bool
    dimension_failures: list[str] = Field(default_factory=list)
    is_resubmission: bool = False
    prior_decision: Optional[str] = None


class LedgerEntry(BaseModel):
    proposal_id: str
    decision: Decision
    score_total: int
    score_breakdown: ScoreBreakdown
    rationale: str
    amount_requested: float
    amount_approved: float
    balance_before: float
    balance_after: float
    hlos_receipt_hash: Optional[str] = None
    decided_at: datetime = Field(default_factory=datetime.utcnow)
    agent_trace_id: str = ""
    # Phase 3 fields
    evaluator_score: Optional[int] = None
    skeptic_score: Optional[int] = None
    coordinator_synthesis: Optional[str] = None
    overrode_evaluator: bool = False
    is_resubmission: bool = False
    # Phase 4 fields
    human_override_by: Optional[str] = None
    human_override_reason: Optional[str] = None
    human_override_at: Optional[datetime] = None
    original_decision: Optional[str] = None
