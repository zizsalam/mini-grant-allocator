"""Flask web interface for the Grant Allocator — Phase 4."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from src.coordinator import coordinate
from src.evaluator import evaluate_proposal
from src.explainer import explain_batch, explain_decision
from src.hlos import HLOSWallet
from src.ledger import Ledger
from src.observability import (
    AgentTrace,
    BatchReport,
    HLOSTrace,
    Timer,
    trace_mock,
    trace_response,
)
from src.schemas import Proposal
from src.skeptic import challenge_proposal
from src.treasury import process_decision

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-key")

PROPOSALS_PATH = "data/sample_proposals.json"
LEDGER_PATH = "ledger.json"
REPORT_PATH = "batch_report.json"

# In-memory store for the latest batch report
_latest_report: dict = {}


def load_proposals() -> list[Proposal]:
    with open(PROPOSALS_PATH) as f:
        return [Proposal(**p) for p in json.load(f)]


def get_ledger_data() -> tuple[list[dict], dict]:
    """Read ledger and compute summary stats."""
    ledger = Ledger(path=LEDGER_PATH)
    entries = ledger.read_all()

    approved = [e for e in entries if e["decision"] == "APPROVED"]
    rejected = [e for e in entries if e["decision"] == "REJECTED"]
    escalated = [e for e in entries if e["decision"] == "ESCALATED"]

    overrides = sum(1 for e in entries if e.get("overrode_evaluator"))
    resubmissions = sum(1 for e in entries if e.get("is_resubmission"))
    human_overrides = sum(1 for e in entries if e.get("human_override_by"))

    # Load report if available
    report = {}
    if Path(REPORT_PATH).exists():
        with open(REPORT_PATH) as f:
            report = json.load(f)

    stats = {
        "approved": len(approved),
        "rejected": len(rejected),
        "escalated": len(escalated),
        "disbursed": sum(e["amount_approved"] for e in approved),
        "balance": entries[-1]["balance_after"] if entries else float(
            os.getenv("HLOS_INITIAL_BALANCE", "10000")
        ),
        "overrides": overrides,
        "resubmissions": resubmissions,
        "human_overrides": human_overrides,
        "llm_cost": report.get("totals", {}).get("llm_cost", 0),
        "total_tokens": report.get("totals", {}).get("total_tokens", 0),
        "total_latency_ms": report.get("totals", {}).get("total_latency_ms", 0),
    }
    return entries, stats


@app.route("/")
def dashboard():
    entries, stats = get_ledger_data()
    report = {}
    if Path(REPORT_PATH).exists():
        with open(REPORT_PATH) as f:
            report = json.load(f)
    return render_template("index.html", entries=entries, stats=stats, report=report)


@app.route("/run", methods=["POST"])
def run_batch():
    """Run a fresh batch evaluation with full observability."""
    global _latest_report

    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    use_mock = not has_api_key
    model = "claude-sonnet-4-6"

    # Fresh wallet and ledger
    from src.staamp import reset_client, get_anthropic_client
    reset_client()  # Clear cached client for fresh credentials

    wallet = HLOSWallet.connect()
    if not use_mock:
        get_anthropic_client(wallet)  # Initialize STAAMP client

    ledger_path = Path(LEDGER_PATH)
    if ledger_path.exists():
        ledger_path.unlink()
    ledger = Ledger(path=LEDGER_PATH)

    proposals = load_proposals()
    results = []
    override_count = 0

    # Phase 4: Initialize batch report
    batch_report = BatchReport(batch_start=datetime.utcnow().isoformat())

    for proposal in proposals:
        # --- Evaluator with tracing ---
        with Timer() as eval_timer:
            evaluation = evaluate_proposal(proposal, use_mock=use_mock, model=model)
        batch_report.add_agent_trace(
            trace_mock("evaluator", proposal.id, eval_timer.elapsed_ms)
            if use_mock else _trace_last_call("evaluator", proposal.id, model, eval_timer.elapsed_ms)
        )

        # --- Skeptic with tracing ---
        with Timer() as skep_timer:
            challenge = challenge_proposal(proposal, evaluation, use_mock=use_mock, model=model)
        batch_report.add_agent_trace(
            trace_mock("skeptic", proposal.id, skep_timer.elapsed_ms)
            if use_mock else _trace_last_call("skeptic", proposal.id, model, skep_timer.elapsed_ms)
        )

        # --- Coordinator with tracing ---
        with Timer() as coord_timer:
            verdict = coordinate(proposal, evaluation, challenge, ledger, use_mock=use_mock, model=model)
        batch_report.add_agent_trace(
            trace_mock("coordinator", proposal.id, coord_timer.elapsed_ms)
            if use_mock else _trace_last_call("coordinator", proposal.id, model, coord_timer.elapsed_ms)
        )

        if verdict.overrode_evaluator:
            override_count += 1

        # --- Treasury with HLOS tracing ---
        bal_before = wallet.get_balance()
        entry = process_decision(
            evaluation, wallet, ledger,
            original_requested_amount=proposal.requested_amount,
            verdict=verdict,
        )
        bal_after = wallet.get_balance()

        if entry.decision.value == "APPROVED":
            batch_report.add_hlos_trace(HLOSTrace(
                operation="notarize",
                proposal_id=proposal.id,
                result="success",
                balance_before=bal_before,
                balance_after=bal_after,
                timestamp=datetime.utcnow().isoformat(),
            ))

        results.append(entry)

    batch_report.batch_end = datetime.utcnow().isoformat()

    # Save batch report with HLOS audit log
    report_data = batch_report.to_dict()
    report_data["hlos_audit_log"] = wallet.audit_log
    report_data["hlos_mode"] = wallet.mode_label
    with open(REPORT_PATH, "w") as f:
        json.dump(report_data, f, indent=2)
    _latest_report = report_data

    approved = sum(1 for r in results if r.decision.value == "APPROVED")
    rejected = sum(1 for r in results if r.decision.value == "REJECTED")
    total_disbursed = sum(r.amount_approved for r in results if r.decision.value == "APPROVED")
    mode = "mock" if use_mock else "Claude"

    cost_str = f", cost ${batch_report.total_llm_cost:.4f}" if not use_mock else ""
    flash(
        f"Batch complete ({mode}, 3-agent panel): {approved} approved, "
        f"{rejected} rejected, {override_count} overrides, "
        f"${total_disbursed:,.0f} disbursed, "
        f"${wallet.get_balance():,.0f} remaining{cost_str}"
    )
    return redirect(url_for("dashboard"))


def _trace_last_call(agent: str, proposal_id: str, model: str, elapsed_ms: float) -> AgentTrace:
    """Create an estimated trace for live API calls.

    Since we don't thread the response object through, we estimate tokens.
    In a production system, responses would be returned alongside results.
    """
    # Rough estimates based on typical usage
    return AgentTrace(
        agent=agent,
        proposal_id=proposal_id,
        input_tokens=800,
        output_tokens=300,
        latency_ms=elapsed_ms,
        cost_estimate=(800 * 3.0 / 1_000_000) + (300 * 15.0 / 1_000_000),
        model=model,
        timestamp=datetime.utcnow().isoformat(),
        is_mock=False,
    )


# --- Phase 4: Explainability endpoint ---

@app.route("/explain/<proposal_id>")
def explain(proposal_id):
    """Plain-language explanation of a single decision."""
    ledger = Ledger(path=LEDGER_PATH)
    entries = ledger.read_all()
    entry = next((e for e in entries if e["proposal_id"] == proposal_id), None)
    if not entry:
        return jsonify({"error": f"Proposal {proposal_id} not found"}), 404
    explanation = explain_decision(entry)
    if request.headers.get("Accept") == "application/json":
        return jsonify({"proposal_id": proposal_id, "explanation": explanation})
    return f"<pre style='background:#0f172a;color:#e2e8f0;padding:2rem;font-family:monospace;white-space:pre-wrap'>{explanation}</pre>"


# --- Phase 4: Human override endpoint ---

@app.route("/override/<proposal_id>", methods=["POST"])
def human_override(proposal_id):
    """Apply a human override to a decision."""
    ledger = Ledger(path=LEDGER_PATH)
    entries = ledger.read_all()

    idx = next((i for i, e in enumerate(entries) if e["proposal_id"] == proposal_id), None)
    if idx is None:
        flash(f"Proposal {proposal_id} not found")
        return redirect(url_for("dashboard"))

    new_decision = request.form.get("decision", "").upper()
    reason = request.form.get("reason", "No reason provided")
    override_by = request.form.get("override_by", "admin")

    if new_decision not in ("APPROVED", "REJECTED", "ESCALATED"):
        flash(f"Invalid decision: {new_decision}")
        return redirect(url_for("dashboard"))

    entry = entries[idx]
    original = entry["decision"]

    # Record the override
    entry["original_decision"] = original
    entry["decision"] = new_decision
    entry["human_override_by"] = override_by
    entry["human_override_reason"] = reason
    entry["human_override_at"] = datetime.utcnow().isoformat()

    # If overriding to REJECTED, zero out the amount
    if new_decision == "REJECTED":
        entry["amount_approved"] = 0.0

    # Write back (this is a rare case where we modify the ledger —
    # the override itself is the audit trail)
    with open(LEDGER_PATH, "w") as f:
        json.dump(entries, f, indent=2, default=str)

    flash(
        f"Override applied: {proposal_id} changed from {original} to "
        f"{new_decision} by {override_by}. Reason: {reason}"
    )
    return redirect(url_for("dashboard"))


# --- Phase 4: Batch report endpoint ---

@app.route("/report")
def batch_report():
    """Full batch report with observability data."""
    entries, stats = get_ledger_data()
    report = {}
    if Path(REPORT_PATH).exists():
        with open(REPORT_PATH) as f:
            report = json.load(f)

    explanation = explain_batch(entries, report)

    if request.headers.get("Accept") == "application/json":
        return jsonify({"report": report, "summary": explanation})
    return render_template("report.html", report=report, entries=entries, stats=stats, explanation=explanation)


@app.route("/api/ledger")
def api_ledger():
    """JSON endpoint for ledger data."""
    entries, stats = get_ledger_data()
    return jsonify({"entries": entries, "stats": stats})


if __name__ == "__main__":
    app.run(debug=True, port=5050)
