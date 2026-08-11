import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal, init_db
from app.main import app
from app.models.customer import Customer
from app.config import get_settings


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
