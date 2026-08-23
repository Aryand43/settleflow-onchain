// injected comes from the wagmi root rather than "wagmi/connectors": that
// barrel eagerly pulls in the Safe and WalletConnect connectors, whose
// optional peer packages are not installed, and the build fails resolving
// them. The root export is the same function without the extra graph.
import { createConfig, http, injected } from "wagmi";
import { defineChain } from "viem";
import type { PaymentPage } from "./api";

/*
 * The chain is described by the API, not hardcoded here.
 *
 * The payment page response carries chain_id, rpc_url and both contract
 * addresses, so the same build works against a local Anvil (31337 on
 * localhost:8545), the hosted Anvil on Modal, or a public testnet — whatever
 * the backend is configured for. Baking a chain into the bundle would mean a
 * rebuild every time the chain moved, and a silent mismatch whenever the
 * frontend and backend disagreed.
 */
export function chainFrom(page: PaymentPage) {
  if (!page.chain_id || !page.rpc_url) return null;
  return defineChain({
    id: page.chain_id,
    name: page.chain_id === 31337 ? "SettleFlow Demo Chain" : `Chain ${page.chain_id}`,
    nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
    rpcUrls: { default: { http: [page.rpc_url] } },
  });
}

export function configFrom(page: PaymentPage) {
  const chain = chainFrom(page);
  // chainFrom already guarantees rpc_url is set, but narrowing it again keeps
  // the http() transport honest without a non-null assertion.
  if (!chain || !page.rpc_url) return null;
  return createConfig({
    chains: [chain],
    // `injected` covers MetaMask and every other extension that follows EIP-1193,
    // including MetaMask mobile's in-app browser. No WalletConnect project id
    // required, which keeps this working with no third-party signup.
    connectors: [injected()],
    transports: { [chain.id]: http(page.rpc_url) },
    ssr: true,
  });
}

// Minimal ABIs — only the three functions this page calls. Mirrors the shape the
// API uses in services/blockchain.py.
export const ROUTER_ABI = [
  {
    type: "function",
    name: "payInvoice",
    inputs: [{ name: "invoiceId", type: "bytes32" }],
    outputs: [],
    stateMutability: "nonpayable",
  },
] as const;

export const ERC20_ABI = [
  {
    type: "function",
    name: "approve",
    inputs: [
      { name: "spender", type: "address" },
      { name: "amount", type: "uint256" },
    ],
    outputs: [{ type: "bool" }],
    stateMutability: "nonpayable",
  },
  {
    type: "function",
    name: "balanceOf",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "allowance",
    inputs: [
      { name: "owner", type: "address" },
      { name: "spender", type: "address" },
    ],
    outputs: [{ type: "uint256" }],
    stateMutability: "view",
  },
] as const;
