"use client";

import { useMemo, useState } from "react";
import { WagmiProvider, useAccount, useChainId } from "wagmi";
import {
  connect,
  readContract,
  switchChain,
  waitForTransactionReceipt,
  writeContract,
} from "wagmi/actions";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Wallet, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui";
import { api, type PaymentPage } from "@/lib/api";
import { ERC20_ABI, ROUTER_ABI, configFrom } from "@/lib/wagmi";
import { formatCurrency } from "@/lib/utils";

/*
 * Pays an invoice from the customer's own wallet.
 *
 * The distinction that matters: the server-side "demo wallet" button signs with
 * DEMO_PAYER_PRIVATE_KEY, so the backend is paying itself. Here the customer's
 * wallet produces the signature and the backend could not have forged it. The
 * settlement path is identical either way — the API rescans the router's
 * InvoicePaid events rather than trusting anything this component reports.
 *
 * Two transactions, because ERC-20 works that way: `approve` grants the router
 * an allowance, `payInvoice` makes the router pull it. Each is a separate
 * wallet prompt, which is why the status text names which one is open.
 */

type Props = {
  page: PaymentPage;
  onPaid: (page: PaymentPage) => void;
};

type Phase =
  | "idle"
  | "registering"
  | "funding"
  | "approving"
  | "paying"
  | "settling"
  | "done";

const PHASE_LABEL: Record<Phase, string> = {
  idle: "",
  registering: "Registering this invoice on-chain…",
  funding: "Sending test funds to your wallet…",
  approving: "Confirm the approval in your wallet…",
  paying: "Confirm the payment in your wallet…",
  settling: "Waiting for on-chain confirmation…",
  done: "Settled.",
};

export function WalletPay({ page, onPaid }: Props) {
  // Rebuilt only when the chain details change. createConfig() sets up
  // connector state, so calling it on every render would drop the connection.
  const config = useMemo(
    () => configFrom(page),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [page.chain_id, page.rpc_url]
  );
  const queryClient = useMemo(() => new QueryClient(), []);

  if (!config) return null;

  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <WalletPayInner page={page} onPaid={onPaid} config={config} />
      </QueryClientProvider>
    </WagmiProvider>
  );
}

function WalletPayInner({
  page,
  onPaid,
  config,
}: Props & { config: NonNullable<ReturnType<typeof configFrom>> }) {
  const { address, isConnected } = useAccount();
  const activeChainId = useChainId();
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);

  const busy = phase !== "idle" && phase !== "done";
  const wrongChain = isConnected && page.chain_id !== null && activeChainId !== page.chain_id;

  async function handleConnect() {
    setError(null);
    try {
      await connect(config, { connector: config.connectors[0] });
    } catch (e) {
      setError(
        e instanceof Error && /no injected|not found|undefined/i.test(e.message)
          ? "No wallet detected. Install MetaMask, or open this link inside your wallet's browser."
          : messageOf(e, "Could not connect to your wallet.")
      );
    }
  }

  async function handleSwitch() {
    setError(null);
    try {
      // wagmi falls back to wallet_addEthereumChain when the wallet has never
      // seen this chain, which is always true for a fresh demo devnet.
      await switchChain(config, { chainId: page.chain_id! });
    } catch (e) {
      setError(messageOf(e, "Could not switch networks. You can also switch manually in your wallet."));
    }
  }

  async function handlePay() {
    if (!address || !page.amount_base_units) return;
    setError(null);
    setTxHash(null);

    const amount = BigInt(page.amount_base_units);
    const router = page.router_address as `0x${string}`;
    const usdc = page.usdc_address as `0x${string}`;
    const invoiceId = page.on_chain_invoice_id as `0x${string}`;

    try {
      // 1. The router must already know this invoice, or payInvoice reverts
      //    with InvalidInvoice. Only the merchant key can register it.
      if (!page.registered_on_chain) {
        setPhase("registering");
        await api.registerByToken(page.payment_token);
      }

      // 2. A wallet that has never touched this chain holds neither gas nor
      //    USDC. In demo mode the API tops it up; otherwise the customer is
      //    expected to already hold both and we let the wallet report the
      //    shortfall itself.
      if (page.demo_mode) {
        const balance = (await readContract(config, {
          address: usdc,
          abi: ERC20_ABI,
          functionName: "balanceOf",
          args: [address],
        })) as bigint;
        if (balance < amount) {
          setPhase("funding");
          await api.fundByToken(page.payment_token, address);
        }
      }

      // 3. Allowance, then payment. Skipped when a previous attempt already
      //    approved enough — re-approving costs the customer a pointless
      //    signature and confuses the flow.
      const allowance = (await readContract(config, {
        address: usdc,
        abi: ERC20_ABI,
        functionName: "allowance",
        args: [address, router],
      })) as bigint;

      if (allowance < amount) {
        setPhase("approving");
        const approveHash = await writeContract(config, {
          address: usdc,
          abi: ERC20_ABI,
          functionName: "approve",
          args: [router, amount],
        });
        await waitForTransactionReceipt(config, { hash: approveHash });
      }

      setPhase("paying");
      const payHash = await writeContract(config, {
        address: router,
        abi: ROUTER_ABI,
        functionName: "payInvoice",
        args: [invoiceId],
      });
      setTxHash(payHash);
      await waitForTransactionReceipt(config, { hash: payHash });

      // 4. Ask the API to reconcile. It rescans InvoicePaid events rather than
      //    taking our word for it, so a lost response here is recoverable by
      //    reloading rather than a stuck invoice.
      setPhase("settling");
      const settled = await api.settleByToken(page.payment_token);
      setPhase("done");
      onPaid(settled);
    } catch (e) {
      setPhase("idle");
      setError(interpret(e));
    }
  }

  return (
    <div>
      <p className="text-sm font-medium text-content">Pay from your own wallet</p>
      <p className="mt-1 text-sm text-content-muted">
        {isConnected
          ? "You'll approve two transactions: one to authorise the amount, one to pay it."
          : "Connect a wallet to sign the payment yourself."}
      </p>

      {isConnected && address && (
        <p className="mt-3 truncate font-mono text-xs text-content-muted">
          {address.slice(0, 6)}…{address.slice(-4)}
        </p>
      )}

      {error && <p className="mt-3 text-xs text-overdue">{error}</p>}

      {busy && (
        <p className="mt-3 text-xs text-content-secondary" aria-live="polite">
          {PHASE_LABEL[phase]}
        </p>
      )}

      {txHash && (
        <p className="mt-2 flex items-center gap-1.5 font-mono text-xs text-content-muted">
          <ExternalLink aria-hidden className="h-3 w-3 shrink-0" />
          <span className="truncate">{txHash}</span>
        </p>
      )}

      {!isConnected ? (
        <Button size="sm" className="mt-3 w-full" onClick={handleConnect}>
          <Wallet aria-hidden className="h-4 w-4" />
          Connect wallet
        </Button>
      ) : wrongChain ? (
        <Button size="sm" className="mt-3 w-full" onClick={handleSwitch}>
          Switch to the demo network
        </Button>
      ) : (
        <Button
          size="sm"
          className="mt-3 w-full"
          onClick={handlePay}
          loading={busy}
          disabled={busy}
        >
          <Wallet aria-hidden className="h-4 w-4" />
          Pay {formatCurrency(page.amount, page.currency)}
        </Button>
      )}
    </div>
  );
}

function messageOf(e: unknown, fallback: string) {
  return e instanceof Error && e.message ? e.message : fallback;
}

/** Turns the wallet's and the chain's error vocabulary into something a payer can act on. */
function interpret(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  if (/User rejected|denied transaction|User denied/i.test(raw)) {
    return "You cancelled that in your wallet. Nothing was charged.";
  }
  if (/AlreadyPaid/i.test(raw)) {
    return "This invoice has already been paid on-chain. Reload the page.";
  }
  if (/InvalidInvoice/i.test(raw)) {
    return "The chain doesn't recognise this invoice yet. Reload and try again.";
  }
  if (/Expired/i.test(raw)) {
    return "The payment window for this invoice has expired. Ask the sender to reissue it.";
  }
  if (/insufficient funds/i.test(raw)) {
    return "Your wallet doesn't have enough gas for this transaction.";
  }
  return raw.split("\n")[0].slice(0, 200) || "That transaction didn't go through.";
}
