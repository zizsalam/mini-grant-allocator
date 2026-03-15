"""Observability — Phase 4.

Tracks token usage, latency, and estimated cost for every agent invocation.
Produces batch summary reports.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# Approximate pricing per 1M tokens (Claude Sonnet 4.6, as of March 2026)
COST_PER_INPUT_TOKEN = 3.00 / 1_000_000   # $3/1M input
COST_PER_OUTPUT_TOKEN = 15.00 / 1_000_000  # $15/1M output


@dataclass
class AgentTrace:
    """Single agent invocation trace."""
    agent: str  # "evaluator", "skeptic", "coordinator"
    proposal_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_estimate: float = 0.0
    model: str = ""
    timestamp: str = ""
    is_mock: bool = False

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "proposal_id": self.proposal_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": round(self.latency_ms, 1),
            "cost_estimate": round(self.cost_estimate, 6),
            "model": self.model,
            "timestamp": self.timestamp,
            "is_mock": self.is_mock,
        }


@dataclass
class HLOSTrace:
    """Single HLOS operation trace."""
    operation: str  # "get_balance", "notarize"
    proposal_id: str
    result: str
    balance_before: float
    balance_after: float
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "proposal_id": self.proposal_id,
            "result": self.result,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "timestamp": self.timestamp,
        }


@dataclass
class BatchReport:
    """Complete batch execution report."""
    agent_traces: list[AgentTrace] = field(default_factory=list)
    hlos_traces: list[HLOSTrace] = field(default_factory=list)
    batch_start: Optional[str] = None
    batch_end: Optional[str] = None

    def add_agent_trace(self, trace: AgentTrace) -> None:
        self.agent_traces.append(trace)

    def add_hlos_trace(self, trace: HLOSTrace) -> None:
        self.hlos_traces.append(trace)

    @property
    def total_input_tokens(self) -> int:
        return sum(t.input_tokens for t in self.agent_traces)

    @property
    def total_output_tokens(self) -> int:
        return sum(t.output_tokens for t in self.agent_traces)

    @property
    def total_llm_cost(self) -> float:
        return sum(t.cost_estimate for t in self.agent_traces)

    @property
    def total_latency_ms(self) -> float:
        return sum(t.latency_ms for t in self.agent_traces)

    @property
    def total_disbursed(self) -> float:
        return sum(
            t.balance_before - t.balance_after
            for t in self.hlos_traces
            if t.operation == "notarize"
        )

    def to_dict(self) -> dict:
        return {
            "batch_start": self.batch_start,
            "batch_end": self.batch_end,
            "totals": {
                "input_tokens": self.total_input_tokens,
                "output_tokens": self.total_output_tokens,
                "total_tokens": self.total_input_tokens + self.total_output_tokens,
                "llm_cost": round(self.total_llm_cost, 4),
                "total_latency_ms": round(self.total_latency_ms, 1),
                "hlos_disbursed": round(self.total_disbursed, 2),
                "agent_calls": len(self.agent_traces),
                "hlos_calls": len(self.hlos_traces),
            },
            "agent_traces": [t.to_dict() for t in self.agent_traces],
            "hlos_traces": [t.to_dict() for t in self.hlos_traces],
        }


class Timer:
    """Context manager for timing operations."""

    def __init__(self):
        self.start_time = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self):
        self.start_time = time.monotonic()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.monotonic() - self.start_time) * 1000


def trace_response(response, agent: str, proposal_id: str, model: str,
                   elapsed_ms: float) -> AgentTrace:
    """Build an AgentTrace from an Anthropic API response."""
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = (input_tokens * COST_PER_INPUT_TOKEN +
            output_tokens * COST_PER_OUTPUT_TOKEN)

    return AgentTrace(
        agent=agent,
        proposal_id=proposal_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=elapsed_ms,
        cost_estimate=cost,
        model=model,
        timestamp=datetime.utcnow().isoformat(),
        is_mock=False,
    )


def trace_mock(agent: str, proposal_id: str, elapsed_ms: float) -> AgentTrace:
    """Build an AgentTrace for a mock agent call."""
    return AgentTrace(
        agent=agent,
        proposal_id=proposal_id,
        input_tokens=0,
        output_tokens=0,
        latency_ms=elapsed_ms,
        cost_estimate=0.0,
        model="mock",
        timestamp=datetime.utcnow().isoformat(),
        is_mock=True,
    )
