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


def pay_invoice_onchain(invoice: Invoice) -> str:
    """Acts as a demo customer wallet: mints itself the owed USDC, approves the
    router, and pays the invoice. Produces a real transaction hash on whatever
    chain RPC_URL points at (a local Anvil devnet by default)."""
    settings = get_settings()
    if not chain_ready(settings) or not settings.demo_payer_private_key:
        raise RuntimeError("Blockchain not configured for on-chain demo payment")

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
