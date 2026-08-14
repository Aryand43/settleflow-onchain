import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal, init_db
from app.main import app
from app.models.activity import ActivityEvent
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.services.invoice import sync_invoice_counter
from app.config import get_settings


@pytest.fixture(autouse=True)
def no_live_chain(monkeypatch):
    # Smoke tests reset the DB (and therefore invoice numbering) on every
    # test, so on-chain invoice IDs would collide across runs against a real,
    # persistent chain. Force the demo fallback path instead of hitting
    # whatever chain happens to be configured in .env for local dev.
    # pydantic-settings reads .env directly, so an unset process env var
    # doesn't hide a value already present in the file — set them to an
    # explicit empty string instead, which does take precedence.
    for var in (
        "RPC_URL",
        "PAYMENT_CONTRACT_ADDRESS",
        "USDC_CONTRACT_ADDRESS",
        "MERCHANT_PRIVATE_KEY",
        "DEMO_PAYER_PRIVATE_KEY",
    ):
        monkeypatch.setenv(var, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(
        Customer(
            name="Daniel Tan",
            email="daniel@example.com",
            wallet_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            company="Tan Design",
        )
    )
    db.commit()
    db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def headers():
    settings = get_settings()
    return {"X-API-Key": settings.api_key}


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_parse_demo_command(client, headers):
    res = client.post(
        "/api/invoices/parse-command",
        json={"command": "Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days."},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["customer_name"] == "Daniel Tan"
    assert data["amount"] == 100
    assert data["currency"] == "USDC"
    assert data["description"] == "website redesign"
    assert data["confidence"] >= 0.9


def test_create_invoice_sequential_number(client, headers):
    res = client.post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "amount": 100,
            "currency": "USDC",
            "description": "website redesign",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        headers=headers,
    )
    assert res.status_code == 201
    assert res.json()["invoice_number"] == "INV-0001"


def test_invoice_numbers_are_not_reused_after_delete(client, headers):
    """The counter hands out each number once. The old count()-based scheme
    would reissue INV-0001 here, which also meant reissuing its
    on_chain_invoice_id — and the router rejects a duplicate invoice id."""
    payload = {
        "customer_id": 1,
        "amount": 10,
        "currency": "USDC",
        "description": "first",
        "due_date": str(date.today() + timedelta(days=7)),
    }
    first = client.post("/api/invoices", json=payload, headers=headers)
    assert first.json()["invoice_number"] == "INV-0001"

    db = SessionLocal()
    try:
        # Activity rows go first: Postgres enforces the foreign key, where
        # SQLite (pragma foreign_keys off by default) would let the orphan slide.
        invoice_id = first.json()["id"]
        db.query(ActivityEvent).filter(ActivityEvent.invoice_id == invoice_id).delete()
        db.query(Invoice).filter(Invoice.id == invoice_id).delete()
        db.commit()
    finally:
        db.close()

    second = client.post("/api/invoices", json={**payload, "description": "second"}, headers=headers)
    assert second.json()["invoice_number"] == "INV-0002"
    assert second.json()["on_chain_invoice_id"] != first.json()["on_chain_invoice_id"]


def test_seeded_numbers_do_not_collide_with_api_created_ones(client, headers):
    """Mirrors scripts/seed.py, which writes invoice numbers by hand and then
    calls sync_invoice_counter() so the API picks up after them."""
    db = SessionLocal()
    try:
        db.add(
            Invoice(
                invoice_number="INV-0009",
                customer_id=1,
                merchant_wallet="0x" + "1" * 40,
                amount=1.0,
                currency="USDC",
                amount_wei_or_base_units=1_000_000,
                description="hand-written",
                due_date=date.today(),
                status=InvoiceStatus.pending.value,
                payment_token="hand-written-token",
            )
        )
        db.commit()
        assert sync_invoice_counter(db) == 10
    finally:
        db.close()

    res = client.post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "amount": 10,
            "currency": "USDC",
            "description": "after seed",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        headers=headers,
    )
    assert res.status_code == 201
    assert res.json()["invoice_number"] == "INV-0010"


def test_large_invoice_amount_survives_base_units(client, headers):
    """5,000 USDC is 5e9 base units — past the 32-bit INTEGER ceiling that
    Postgres (unlike SQLite) actually enforces."""
    res = client.post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "amount": 5000,
            "currency": "USDC",
            "description": "large",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        headers=headers,
    )
    assert res.status_code == 201
    assert res.json()["amount_wei_or_base_units"] == 5_000_000_000


def test_simulate_payment_demo_mode(client, headers, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()

    create = client.post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "amount": 50,
            "currency": "USDC",
            "description": "test",
            "due_date": str(date.today() + timedelta(days=3)),
        },
        headers=headers,
    )
    invoice_id = create.json()["id"]

    res = client.post(f"/api/invoices/{invoice_id}/simulate-payment", headers=headers)
    assert res.status_code == 200
    assert res.json()["invoice"]["status"] == "paid"
    assert res.json()["invoice"]["blockchain_tx_hash"]


def test_simulate_payment_idempotent(client, headers, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()

    create = client.post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "amount": 50,
            "currency": "USDC",
            "description": "test",
            "due_date": str(date.today() + timedelta(days=3)),
        },
        headers=headers,
    )
    invoice_id = create.json()["id"]
    client.post(f"/api/invoices/{invoice_id}/simulate-payment", headers=headers)
    res = client.post(f"/api/invoices/{invoice_id}/simulate-payment", headers=headers)
    assert res.status_code == 200
    assert "Already paid" in res.json()["message"]


def test_simulate_time_marks_overdue(client, headers):
    create = client.post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "amount": 75,
            "currency": "USDC",
            "description": "overdue test",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        headers=headers,
    )
    invoice_id = create.json()["id"]

    res = client.post(f"/api/invoices/{invoice_id}/simulate-time", headers=headers)
    assert res.status_code == 200
    assert res.json()["invoice"]["status"] == "overdue"

    activity = client.get(f"/api/invoices/{invoice_id}/activity", headers=headers)
    types = [e["event_type"] for e in activity.json()]
    assert "invoice_overdue" in types
