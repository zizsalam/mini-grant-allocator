import 'dotenv/config';
import { SolanaSDK, IPFSClient, buildRegistrationFileJson, ServiceType } from '8004-solana';
import { Keypair } from '@solana/web3.js';

async function main() {
  const signer = Keypair.fromSecretKey(
    Uint8Array.from(JSON.parse(process.env.SOLANA_PRIVATE_KEY!))
  );

  const sdk = new SolanaSDK({ signer });

  // 1. Create collection for the grant allocator system
  const collection = await sdk.createCollection({
    name: 'Grant Allocator System',
    symbol: 'GRANT',
    description: 'Autonomous grant evaluation and disbursement agents powered by HLOS',
    socials: { website: 'https://github.com/zizsalam/mini-grant-allocator' },
  });
  console.log('Collection pointer:', collection.pointer);

  // 2. Register evaluator agent
  const evalMeta = buildRegistrationFileJson({
    name: 'Grant Evaluator Agent',
    description:
      'Scores grant proposals 0-100 across 5 dimensions (team, impact, budget, alignment, risk). ' +
      'Returns structured JSON verdict with per-dimension rationale. ' +
      'Part of a 3-agent panel: evaluator + skeptic + coordinator.',
    skills: ['natural_language_processing/text_generation/text_generation'],
    domains: ['finance/grants/grant_evaluation'],
    services: [
      { type: ServiceType.MCP, value: 'https://YOUR_DOMAIN/mcp' },
    ],
  });

  const ipfs = new IPFSClient({
    pinataEnabled: !!process.env.PINATA_JWT,
    pinataJwt: process.env.PINATA_JWT!,
  });

  const evalCid = await ipfs.addJson(evalMeta);
  const evalAgent = await sdk.registerAgent(`ipfs://${evalCid}`, {
    collectionPointer: collection.pointer,
  });
  console.log('EVALUATOR_AGENT_ASSET=', evalAgent.asset!.toBase58());

  // 3. Register treasury agent with operational wallet
  const treasuryMeta = buildRegistrationFileJson({
    name: 'Grant Treasury Agent',
    description:
      'Holds budget, enforces constraints via HLOS wallet, disburses approved grants. ' +
      'Budget enforcement is infrastructure-level: balance hits zero, no further approvals execute. ' +
      'Every disbursement produces a notarized receipt with cryptographic hash.',
    skills: ['finance/treasury/treasury_management'],
    domains: ['finance/grants/grant_disbursement'],
    services: [
      { type: ServiceType.A2A, value: 'https://YOUR_DOMAIN/a2a' },
    ],
  });

  const treasuryCid = await ipfs.addJson(treasuryMeta);
  const treasuryAgent = await sdk.registerAgent(`ipfs://${treasuryCid}`, {
    collectionPointer: collection.pointer,
  });

  // Create operational wallet for treasury agent
  const opWallet = Keypair.generate();
  await sdk.setAgentWallet(treasuryAgent.asset!, opWallet);

  console.log('TREASURY_AGENT_ASSET=', treasuryAgent.asset!.toBase58());
  console.log('TREASURY_WALLET_PUBLIC=', opWallet.publicKey.toBase58());
  console.log('TREASURY_WALLET_SECRET=', JSON.stringify(Array.from(opWallet.secretKey)));
  console.log('\nCopy the values above into solana/.env');
}

main().catch(console.error);
