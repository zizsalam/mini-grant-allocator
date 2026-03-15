import 'dotenv/config';
import { SolanaSDK } from '8004-solana';
import { Keypair, PublicKey } from '@solana/web3.js';

// Called by Python batch runner: npx ts-node feedback.ts <score> [<ipfs_cid>]
const [,, score, feedbackUri] = process.argv;

if (!score) {
  console.error('Usage: ts-node feedback.ts <score> [<batch_summary_ipfs_cid>]');
  process.exit(1);
}

async function main() {
  const signer = Keypair.fromSecretKey(
    Uint8Array.from(JSON.parse(process.env.SOLANA_PRIVATE_KEY!))
  );
  const sdk = new SolanaSDK({ signer });
  const treasuryAsset = new PublicKey(process.env.TREASURY_AGENT_ASSET!);

  console.log(`Submitting feedback: score=${score}, uri=${feedbackUri ?? 'placeholder'}`);

  await sdk.giveFeedback(treasuryAsset, {
    value: score,
    tag1: 'grant_decisions',
    tag2: 'batch',
    feedbackUri: feedbackUri ?? 'ipfs://QmPlaceholder',
  });

  const summary = await sdk.getSummary(treasuryAsset);
  console.log(
    `Reputation updated. Average score: ${summary.averageScore}, ` +
    `Total batches: ${summary.totalFeedbacks}`
  );
}

main().catch(console.error);
