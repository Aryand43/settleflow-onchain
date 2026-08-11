export const paymentRouterAbi = [
  {
    type: "function",
    name: "payInvoice",
    inputs: [{ name: "invoiceId", type: "bytes32" }],
    outputs: [],
    stateMutability: "nonpayable",
  },
] as const;

export const erc20Abi = [
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
    name: "allowance",
    inputs: [
      { name: "owner", type: "address" },
      { name: "spender", type: "address" },
    ],
    outputs: [{ type: "uint256" }],
    stateMutability: "view",
  },
] as const;

export const CHAIN_ID = process.env.NEXT_PUBLIC_CHAIN_ID
  ? Number(process.env.NEXT_PUBLIC_CHAIN_ID)
  : undefined;

export const RPC_URL = process.env.NEXT_PUBLIC_RPC_URL;
export const PAYMENT_CONTRACT = process.env.NEXT_PUBLIC_PAYMENT_CONTRACT_ADDRESS as `0x${string}` | undefined;
export const USDC_CONTRACT = process.env.NEXT_PUBLIC_USDC_CONTRACT_ADDRESS as `0x${string}` | undefined;

export const chainConfigured = Boolean(CHAIN_ID && RPC_URL && PAYMENT_CONTRACT && USDC_CONTRACT);
