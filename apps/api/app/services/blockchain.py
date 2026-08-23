from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.activity import ActivityEvent, EventType
from app.models.invoice import Invoice, InvoiceStatus
from app.services.invoice import log_activity, mark_paid


PAYMENT_ROUTER_ABI = [
    {
        "type": "function",
        "name": "createPaymentRequest",
        "inputs": [
            {"name": "invoiceId", "type": "bytes32"},
            {"name": "token", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "expiry", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "payInvoice",
        "inputs": [{"name": "invoiceId", "type": "bytes32"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "getPaymentRequest",
        "inputs": [{"name": "invoiceId", "type": "bytes32"}],
        "outputs": [
            {"name": "merchant", "type": "address"},
            {"name": "token", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "expiry", "type": "uint256"},
            {"name": "paid", "type": "bool"},
            {"name": "exists", "type": "bool"},
        ],
        "stateMutability": "view",
    },
]

ERC20_MINT_ABI = [
    {
        "type": "function",
        "name": "mint",
        "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "approve",
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "outputs": [{"type": "bool"}],
        "stateMutability": "nonpayable",
    },
]


def chain_ready(settings) -> bool:
    return bool(
        settings.rpc_url
        and settings.payment_contract_address
        and settings.usdc_contract_address
        and settings.merchant_private_key
    )


def _bytes32(hex_id: str) -> bytes:
    return bytes.fromhex(hex_id[2:] if hex_id.startswith("0x") else hex_id)


def _send(w3, account, fn) -> str:
    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    hex_hash = tx_hash.hex()
    return hex_hash if hex_hash.startswith("0x") else "0x" + hex_hash


def register_payment_request(invoice: Invoice) -> str | None:
    """Registers the invoice on-chain so it can later be paid. Called on invoice
    creation when a chain is configured; a no-op (returns None) otherwise."""
    settings = get_settings()
    if not chain_ready(settings):
        return None

    from eth_account import Account
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    account = Account.from_key(settings.merchant_private_key)
    router = w3.eth.contract(
        address=Web3.to_checksum_address(settings.payment_contract_address),
        abi=PAYMENT_ROUTER_ABI,
    )
    expiry = int((datetime.utcnow() + timedelta(days=30)).timestamp())
    fn = router.functions.createPaymentRequest(
        _bytes32(invoice.on_chain_invoice_id),
        Web3.to_checksum_address(settings.usdc_contract_address),
        invoice.amount_wei_or_base_units,
        expiry,
    )
    return _send(w3, account, fn)


def payment_request_state(invoice: Invoice) -> tuple[bool, bool]:
    """(exists, paid) for this invoice as the router sees it."""
    settings = get_settings()
    if not chain_ready(settings) or not invoice.on_chain_invoice_id:
        return (False, False)

    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    router = w3.eth.contract(
        address=Web3.to_checksum_address(settings.payment_contract_address),
        abi=PAYMENT_ROUTER_ABI,
    )
    request = router.functions.getPaymentRequest(_bytes32(invoice.on_chain_invoice_id)).call()
    return (bool(request[5]), bool(request[4]))


def payment_request_exists(invoice: Invoice) -> bool:
    """Whether the router already knows about this invoice."""
    return payment_request_state(invoice)[0]


def pay_invoice_onchain(invoice: Invoice) -> str | None:
    """Acts as a demo customer wallet: mints itself the owed USDC, approves the
    router, and pays the invoice. Produces a real transaction hash on whatever
    chain RPC_URL points at (a local Anvil devnet by default)."""
    settings = get_settings()
    if not chain_ready(settings) or not settings.demo_payer_private_key:
        raise RuntimeError("Blockchain not configured for on-chain demo payment")

    exists, already_paid = payment_request_state(invoice)

    if already_paid:
        # The chain has settled this invoice; only our row is behind — a payment
        # whose transaction landed while the response was lost, or a database
        # reset over a chain that kept its state. Paying again reverts with
        # AlreadyPaid, so don't. The caller's event scan reconciles the row from
        # the InvoicePaid event, which is the correct direction: the chain is
        # the source of truth for paid, in both directions.
        return None

    # Register on demand if the router has never seen this invoice. Two ways
    # that happens, both routine: scripts/seed.py writes invoices straight to
    # the database without touching the chain, and restarting Anvil wipes every
    # request while the database keeps the rows. Without this, paying either one
    # reverts with InvalidInvoice and surfaces as an opaque 500.
    if not exists:
        register_payment_request(invoice)

    from eth_account import Account
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    payer = Account.from_key(settings.demo_payer_private_key)
    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(settings.usdc_contract_address), abi=ERC20_MINT_ABI
    )
    router = w3.eth.contract(
        address=Web3.to_checksum_address(settings.payment_contract_address), abi=PAYMENT_ROUTER_ABI
    )

    _send(w3, payer, usdc.functions.mint(payer.address, invoice.amount_wei_or_base_units))
    _send(
        w3,
        payer,
        usdc.functions.approve(
            Web3.to_checksum_address(settings.payment_contract_address),
            invoice.amount_wei_or_base_units,
        ),
    )
    return _send(w3, payer, router.functions.payInvoice(_bytes32(invoice.on_chain_invoice_id)))


def scan_blockchain_events(db: Session) -> dict:
    settings = get_settings()
    if not settings.rpc_url or not settings.payment_contract_address:
        return {"processed": 0, "message": "Blockchain not configured"}

    try:
        from web3 import Web3

        w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
        if not w3.is_connected():
            return {"processed": 0, "message": "RPC connection failed"}

        # Minimal ABI for InvoicePaid event
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.payment_contract_address),
            abi=[
                {
                    "anonymous": False,
                    "inputs": [
                        {"indexed": True, "name": "invoiceId", "type": "bytes32"},
                        {"indexed": True, "name": "payer", "type": "address"},
                        {"indexed": True, "name": "merchant", "type": "address"},
                        {"indexed": False, "name": "token", "type": "address"},
                        {"indexed": False, "name": "amount", "type": "uint256"},
                    ],
                    "name": "InvoicePaid",
                    "type": "event",
                }
            ],
        )

        events = contract.events.InvoicePaid.get_logs(from_block=0, to_block="latest")
        processed = 0
        for event in events:
            invoice_id_hex = event["args"]["invoiceId"].hex()
            if not invoice_id_hex.startswith("0x"):
                invoice_id_hex = "0x" + invoice_id_hex

            invoice = db.query(Invoice).filter(Invoice.on_chain_invoice_id == invoice_id_hex).first()
            if not invoice or invoice.blockchain_tx_hash:
                continue

            tx_hash = event["transactionHash"].hex()
            if not tx_hash.startswith("0x"):
                tx_hash = "0x" + tx_hash
            mark_paid(db, invoice, tx_hash, simulated=False)
            processed += 1

        return {"processed": processed, "message": "Scan complete"}
    except Exception as exc:
        return {"processed": 0, "message": str(exc)}


def ensure_registered(invoice: Invoice) -> bool:
    """Registers the invoice on the router if it isn't already.

    Returns True when the router knows about the invoice by the time this
    returns. The customer-pays-from-their-own-wallet flow needs this as a
    separate step: `payInvoice` reverts with InvalidInvoice against an
    unregistered id, and only the merchant key can register.
    """
    if payment_request_exists(invoice):
        return True
    register_payment_request(invoice)
    return payment_request_exists(invoice)


def fund_wallet(address: str, amount_base_units: int) -> dict:
    """Gives an address enough gas and USDC to pay one invoice.

    Two different mechanisms, because they are two different kinds of asset:

    - USDC is minted. `MockUSDC.mint` is deliberately permissionless, so this is
      an ordinary transaction signed by the merchant key.
    - Gas cannot be minted. On Anvil we use `anvil_setBalance`, a devnet cheat
      code that sets an account's ETH balance outright. On a real testnet that
      method does not exist, so we fall back to transferring a small amount from
      the merchant account, which must itself be funded from a faucet.
    """
    settings = get_settings()
    if not chain_ready(settings):
        raise RuntimeError("Blockchain not configured")

    from eth_account import Account
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    merchant = Account.from_key(settings.merchant_private_key)
    payee = Web3.to_checksum_address(address)

    gas_method = "anvil_setBalance"
    try:
        # 10 ETH, far more than a few transactions need, and worthless.
        w3.provider.make_request("anvil_setBalance", [payee, hex(10 * 10**18)])
        if w3.eth.get_balance(payee) == 0:
            raise ValueError("setBalance had no effect")
    except Exception:
        gas_method = "transfer"
        if w3.eth.get_balance(payee) < w3.to_wei(0.002, "ether"):
            tx = {
                "from": merchant.address,
                "to": payee,
                "value": w3.to_wei(0.002, "ether"),
                "nonce": w3.eth.get_transaction_count(merchant.address),
                "gas": 21000,
                "gasPrice": w3.eth.gas_price,
                "chainId": w3.eth.chain_id,
            }
            signed = merchant.sign_transaction(tx)
            w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed.raw_transaction))

    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(settings.usdc_contract_address), abi=ERC20_MINT_ABI
    )
    mint_hash = _send(w3, merchant, usdc.functions.mint(payee, amount_base_units))
    return {"gas_method": gas_method, "mint_tx": mint_hash}
