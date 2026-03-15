import 'dotenv/config';
import express from 'express';
import { execSync } from 'child_process';
import * as path from 'path';

// x402 payment amount per evaluation (in USDC)
const PRICE_USDC = '0.10';
const TREASURY_WALLET = process.env.TREASURY_WALLET_PUBLIC!;
const PROJECT_ROOT = path.resolve(__dirname, '..');

/**
 * Call the Python evaluator via subprocess.
 * Sends the proposal text, gets back the structured JSON evaluation.
 */
async function runEvaluator(proposal: string): Promise<object> {
  const escapedProposal = proposal.replace(/'/g, "'\\''");
  const pythonScript = `
import json, sys, os
sys.path.insert(0, '${PROJECT_ROOT}')
os.chdir('${PROJECT_ROOT}')
from dotenv import load_dotenv
load_dotenv()
from src.evaluator import evaluate_proposal
from src.schemas import Proposal
from datetime import datetime

proposal = Proposal(
    id="X402-REQ",
    title="External Evaluation Request",
    text='''${escapedProposal}''',
    requested_amount=0,
    applicant_id="x402-caller",
    submitted_at=datetime.utcnow(),
)
result = evaluate_proposal(proposal, use_mock=False)
print(json.dumps({
    "proposal_id": result.proposal_id,
    "score_total": result.score_total,
    "score_breakdown": result.score_breakdown.dict(),
    "recommended_amount": result.recommended_amount,
    "rationale": result.rationale,
    "dimension_failures": result.dimension_failures,
    "flags": result.flags,
}))
`;

  try {
    const output = execSync(
      `${PROJECT_ROOT}/.venv/bin/python -c '${pythonScript.replace(/'/g, "'\\''")}'`,
      { timeout: 30000, encoding: 'utf-8', cwd: PROJECT_ROOT }
    );
    return JSON.parse(output.trim());
  } catch (err: any) {
    console.error('Evaluator subprocess failed:', err.stderr || err.message);
    throw new Error('Evaluator failed');
  }
}

/**
 * Verify x402 payment proof.
 * TODO: Replace with real x402 proof verification from x402.org
 * For devnet testing, we accept any non-empty proof header.
 */
async function verifyPayment(proof: string): Promise<boolean> {
  // Production: verify the Solana transaction signature in the proof,
  // confirm USDC transfer to TREASURY_WALLET of >= PRICE_USDC amount,
  // and check that the transaction is finalized on-chain.
  // See: https://x402.org for full verification spec.
  return !!proof;
}

const app = express();
app.use(express.json());

app.post('/evaluate', async (req, res) => {
  const paymentProof = req.headers['x-payment-proof'] as string;

  if (!paymentProof) {
    // Return 402 with x402 payment instructions
    return res.status(402).json({
      accepts: [{
        scheme: 'exact',
        network: 'solana-devnet',        // change to 'solana' for mainnet
        maxAmountRequired: PRICE_USDC,
        resource: 'grant_evaluation',
        payTo: TREASURY_WALLET,
        memo: 'grant-eval',
      }],
      error: 'Payment required to access grant evaluation',
    });
  }

  const valid = await verifyPayment(paymentProof);
  if (!valid) {
    return res.status(402).json({ error: 'Invalid payment proof' });
  }

  const proposal = req.body.proposal;
  if (!proposal) {
    return res.status(400).json({ error: 'proposal field required in request body' });
  }

  try {
    const result = await runEvaluator(proposal);
    res.json(result);
  } catch {
    res.status(500).json({ error: 'Evaluation failed' });
  }
});

app.get('/health', (_, res) => {
  res.json({
    status: 'ok',
    wallet: TREASURY_WALLET,
    price: `${PRICE_USDC} USDC`,
    network: 'solana-devnet',
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`x402 evaluator server running on :${PORT}`);
  console.log(`Treasury wallet: ${TREASURY_WALLET}`);
  console.log(`Price per evaluation: ${PRICE_USDC} USDC`);
});
