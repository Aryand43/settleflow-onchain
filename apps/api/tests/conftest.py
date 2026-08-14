"""Keeps the test suite from touching anything outside this machine.

Two things in `.env` are live: the database and the mail account. Tests drop
every table between cases and exercise the send paths, so left unguarded a
`pytest` run would wipe hosted data and put real email in someone's inbox.

Both are pinned here, before anything imports `app.database` or `app.config`,
because an environment variable takes precedence over the value in `.env` and
`app.database` builds its engine at import time.
"""

import os

# --- Database: a throwaway local file, never the hosted one ---
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "sqlite:///./test_settleflow.db"
)

# --- Email: blank counts as unconfigured, so the suite writes preview files
# instead of connecting to a mail server. Deleting these lines makes `pytest`
# send real mail to whatever addresses the fixtures happen to use. ---
for _var in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM"):
    os.environ[_var] = ""

# --- Chain: never sign a transaction against a real RPC ---
for _var in (
    "RPC_URL",
    "PAYMENT_CONTRACT_ADDRESS",
    "USDC_CONTRACT_ADDRESS",
    "MERCHANT_PRIVATE_KEY",
    "DEMO_PAYER_PRIVATE_KEY",
    "LLM_API_KEY",
):
    os.environ[_var] = ""

from app.database import engine  # noqa: E402

if not os.environ.get("TEST_DATABASE_URL"):
    assert engine.url.get_backend_name() == "sqlite", (
        f"Tests must run against SQLite, got {engine.url.render_as_string(hide_password=True)}. "
        "Something imported app.database before conftest set DATABASE_URL."
    )


def pytest_configure(config):
    """Fails the run rather than quietly sending email if the guard is bypassed."""
    from app.config import get_settings
    from app.services.email import email_delivery_configured

    get_settings.cache_clear()
    assert not email_delivery_configured(), (
        "Email delivery is configured during tests — a run would send real mail. "
        "Check that nothing re-set SMTP_* after conftest."
    )


# Set TEST_DATABASE_URL to run the suite against Postgres instead — e.g.
#
#   docker run -d --name settleflow-pg -e POSTGRES_PASSWORD=devpass \
#       -e POSTGRES_DB=settleflow -p 55432:5432 postgres:16
#   TEST_DATABASE_URL=postgresql://postgres:devpass@127.0.0.1:55432/settleflow \
#       .venv/bin/pytest tests -q
#
# Point that at a scratch database only. It gets dropped.
