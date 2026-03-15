import 'dotenv/config';
import { SolanaSDK, ServiceType } from '8004-solana';
import { Keypair } from '@solana/web3.js';

// Raw GitHub URLs for agent metadata (< 250 bytes each)
const REPO_RAW = 'https://raw.githubusercontent.com/zizsalam/mini-grant-allocator/main/solana';
const EVAL_URI = `${REPO_RAW}/eval-meta.json`;
const TREASURY_URI = `${REPO_RAW}/treasury-meta.json`;
const COLLECTION_URI = `${REPO_RAW}/eval-meta.json`; // reuse for collection

async function main() {
  const signer = Keypair.fromSecretKey(
    Uint8Array.from(JSON.parse(process.env.SOLANA_PRIVATE_KEY!))
  );

  const sdk = new SolanaSDK({ signer });

  // 1. Create collection (on-chain, short URI)
  console.log('Creating collection...');
  const collection = await sdk.createCollection('Grant Allocator System', COLLECTION_URI);
  const collectionKey = collection.collection;
  console.log('Collection:', collectionKey?.toBase58() ?? '(created)');

  // 2. Register evaluator agent
  console.log('Registering evaluator agent...');
  const evalAgent = await sdk.registerAgent(EVAL_URI, {
    collectionPointer: collectionKey?.toBase58(),
  });
  console.log('EVALUATOR_AGENT_ASSET=', evalAgent.asset!.toBase58());

  // 3. Register treasury agent
  console.log('Registering treasury agent...');
  const treasuryAgent = await sdk.registerAgent(TREASURY_URI, {
    collectionPointer: collectionKey?.toBase58(),
  });

  // 4. Create operational wallet for treasury
  console.log('Setting up treasury wallet...');
  const opWallet = Keypair.generate();
  await sdk.setAgentWallet(treasuryAgent.asset!, opWallet);

  console.log('\n========================================');
  console.log('  Registration Complete!');
  console.log('========================================');
  console.log(`EVALUATOR_AGENT_ASSET=${evalAgent.asset!.toBase58()}`);
  console.log(`TREASURY_AGENT_ASSET=${treasuryAgent.asset!.toBase58()}`);
  console.log(`TREASURY_WALLET_PUBLIC=${opWallet.publicKey.toBase58()}`);
  console.log(`TREASURY_WALLET_SECRET=${JSON.stringify(Array.from(opWallet.secretKey))}`);
  console.log('\nCopy the values above into solana/.env');
}

main().catch(console.error);
