import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal, init_db
from app.main import app
from app.models.activity import ActivityEvent
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.services.auth import create_user
from app.services.invoice import sync_invoice_counter
from app.config import get_settings
from app.deps import DEMO_USER_EMAIL


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
        "LLM_API_KEY",
    ):
        monkeypatch.setenv(var, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def setup_db():
    """Fresh schema plus the demo account, which is who X-API-Key resolves to."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    user = create_user(
        db,
        email=DEMO_USER_EMAIL,
        password="settleflow",
        name="Alex Chen",
        wallet_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    )
    db.add(
        Customer(
            owner_id=user.id,
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


def test_cors_allows_next_fallback_port(client):
    res = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3001"


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
                owner_id=1,
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
        assert sync_invoice_counter(db, 1) == 10
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


def test_chat_requires_api_key(client):
    res = client.get("/api/chat/status")
    assert res.status_code == 401


def test_chat_status_unconfigured(client, headers):
    res = client.get("/api/chat/status", headers=headers)
    assert res.status_code == 200
    assert res.json()["configured"] is False


def test_chat_503_without_llm_key(client, headers):
    res = client.post(
        "/api/chat",
        json={"message": "Who is overdue?", "scope": "overview"},
        headers=headers,
    )
    assert res.status_code == 503
    assert "LLM_API_KEY" in res.json()["detail"]


# --- Auth and per-account isolation ---


def _signup(client, email, name="Freelancer"):
    res = client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": "hunter2hunter2"},
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _add_customer(client, headers, name, email):
    res = client.post("/api/customers", json={"name": name, "email": email}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _make_invoice(client, headers, customer_id, amount=100):
    res = client.post(
        "/api/invoices",
        json={
            "customer_id": customer_id,
            "amount": amount,
            "currency": "USDC",
            "description": "work",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_signup_login_and_me(client):
    headers = _signup(client, "alice@example.com", name="Alice")

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"

    login = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "hunter2hunter2"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["name"] == "Alice"

    wrong = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "not-the-password"}
    )
    assert wrong.status_code == 401
    # Same message whether the account exists or not, so responses don't
    # enumerate registered emails.
    assert wrong.json()["detail"] == "Email or password is incorrect"

    missing = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "hunter2hunter2"}
    )
    assert missing.json()["detail"] == wrong.json()["detail"]


def test_signup_rejects_duplicate_email(client):
    _signup(client, "dupe@example.com")
    res = client.post(
        "/api/auth/signup",
        json={"name": "Other", "email": "dupe@example.com", "password": "hunter2hunter2"},
    )
    assert res.status_code == 409


def test_requests_without_credentials_are_rejected(client):
    assert client.get("/api/invoices").status_code == 401
    assert client.get("/api/dashboard/summary").status_code == 401
    assert client.get("/api/customers").status_code == 401
    assert client.post("/api/agent/run-collections").status_code == 401


def test_accounts_cannot_see_each_others_data(client):
    alice = _signup(client, "alice@example.com", name="Alice")
    bob = _signup(client, "bob@example.com", name="Bob")

    alice_customer = _add_customer(client, alice, "Alice Client", "client@alicecorp.example.com")
    bob_customer = _add_customer(client, bob, "Bob Client", "client@bobcorp.example.com")

    alice_invoice = _make_invoice(client, alice, alice_customer, amount=100)
    bob_invoice = _make_invoice(client, bob, bob_customer, amount=999)

    # Lists are disjoint.
    alice_list = client.get("/api/invoices", headers=alice).json()
    assert [i["id"] for i in alice_list] == [alice_invoice["id"]]
    bob_list = client.get("/api/invoices", headers=bob).json()
    assert [i["id"] for i in bob_list] == [bob_invoice["id"]]

    # Direct id access across accounts is a 404, not a 403 — a 403 would
    # confirm the invoice exists.
    assert client.get(f"/api/invoices/{bob_invoice['id']}", headers=alice).status_code == 404
    assert client.get(f"/api/invoices/{bob_invoice['id']}/activity", headers=alice).status_code == 404
    assert client.post(f"/api/invoices/{bob_invoice['id']}/simulate-payment", headers=alice).status_code == 404
    assert client.post(f"/api/invoices/{bob_invoice['id']}/send-reminder", headers=alice).status_code == 404

    # Customer directories are separate, and you can't invoice someone else's customer.
    assert [c["id"] for c in client.get("/api/customers", headers=alice).json()] == [alice_customer]
    cross = client.post(
        "/api/invoices",
        json={
            "customer_id": bob_customer,
            "amount": 10,
            "currency": "USDC",
            "description": "not mine",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        headers=alice,
    )
    assert cross.status_code == 404

    # Dashboard totals don't blend.
    assert client.get("/api/dashboard/summary", headers=alice).json()["total_outstanding"] == 100
    assert client.get("/api/dashboard/summary", headers=bob).json()["total_outstanding"] == 999


def test_each_account_numbers_invoices_from_one(client):
    alice = _signup(client, "alice@example.com")
    bob = _signup(client, "bob@example.com")
    alice_customer = _add_customer(client, alice, "A", "a@acme.example.com")
    bob_customer = _add_customer(client, bob, "B", "b@acme.example.com")

    first = _make_invoice(client, alice, alice_customer)
    second = _make_invoice(client, bob, bob_customer)

    assert first["invoice_number"] == "INV-0001"
    assert second["invoice_number"] == "INV-0001"
    # Same number, different accounts — so the on-chain id must still differ,
    # or the router rejects the second createPaymentRequest as a duplicate.
    assert first["on_chain_invoice_id"] != second["on_chain_invoice_id"]


def test_invoice_is_paid_to_the_owners_wallet(client):
    headers = _signup(client, "wallet@example.com")
    customer = _add_customer(client, headers, "C", "c@acme.example.com")
    invoice = _make_invoice(client, headers, customer)
    me = client.get("/api/auth/me", headers=headers).json()
    assert invoice["merchant_wallet"] == me["wallet_address"]


# --- Customer directory ---


def test_add_customer_and_reject_duplicate_email(client, headers):
    res = client.post(
        "/api/customers",
        json={"name": "New Client", "email": "New.Client@Example.com", "company": "Acme"},
        headers=headers,
    )
    assert res.status_code == 201
    assert res.json()["email"] == "new.client@example.com"  # normalized

    again = client.post(
        "/api/customers", json={"name": "Duplicate", "email": "new.client@example.com"}, headers=headers
    )
    assert again.status_code == 409


def test_csv_import(client, headers):
    csv_body = (
        "Customer Name,Email Address,Company,Wallet\n"
        "Priya Nair,priya@example.com,Nair Studio,0x1111111111111111111111111111111111111111\n"
        "Wei Jie,weijie@example.com,,\n"
        "Broken Row,not-an-email,,\n"
        "Daniel Tan,daniel@example.com,,\n"
        "Dupe In File,dupe@example.com,,\n"
        "Dupe Again,dupe@example.com,,\n"
        "\n"
    )
    res = client.post(
        "/api/customers/import",
        files={"file": ("customers.csv", csv_body, "text/csv")},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["imported"] == 3          # Priya, Wei Jie, Dupe In File
    assert data["skipped"] == 3           # bad email, existing Daniel, second dupe
    assert len(data["errors"]) == 1
    assert "Line 4" in data["errors"][0]

    names = {c["name"] for c in client.get("/api/customers", headers=headers).json()}
    assert {"Priya Nair", "Wei Jie", "Daniel Tan"} <= names


def test_csv_import_requires_name_and_email_columns(client, headers):
    res = client.post(
        "/api/customers/import",
        files={"file": ("bad.csv", "phone,notes\n123,hi\n", "text/csv")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "name column" in res.json()["detail"]


# --- Email delivery honesty ---


def test_email_status_reports_unconfigured(client, headers):
    res = client.get("/api/email/status", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"configured": False, "from_address": None}


def test_send_says_nothing_was_sent_when_smtp_is_unconfigured(client, headers):
    """The button used to report plain success for an email that only ever hit
    the filesystem. The response must say so, and `delivered` must be false."""
    create = client.post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "amount": 100,
            "currency": "USDC",
            "description": "email test",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        headers=headers,
    )
    invoice_id = create.json()["id"]

    res = client.post(f"/api/invoices/{invoice_id}/send", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["delivered"] is False
    assert "not configured" in body["message"]
    assert "nothing was sent" in body["message"]

    # The timeline has to agree with the banner.
    activity = client.get(f"/api/invoices/{invoice_id}/activity", headers=headers).json()
    sent_events = [e for e in activity if e["event_type"] == "invoice_sent"]
    assert sent_events and "drafted" in sent_events[0]["message"]
    assert sent_events[0]["metadata"]["delivered"] is False


def test_reminder_reports_delivery_state(client, headers):
    create = client.post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "amount": 100,
            "currency": "USDC",
            "description": "reminder test",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        headers=headers,
    )
    invoice_id = create.json()["id"]

    res = client.post(f"/api/invoices/{invoice_id}/send-reminder", headers=headers)
    assert res.status_code == 200
    assert res.json()["delivered"] is False
    assert "nothing was sent" in res.json()["message"]
