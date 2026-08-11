from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.activity import ActivityEvent, EventType
from app.models.invoice import Invoice, InvoiceStatus
from app.services.invoice import log_activity, mark_paid


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

        events = contract.events.InvoicePaid.get_logs(fromBlock=0, toBlock="latest")
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
