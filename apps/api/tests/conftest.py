"""Pins the test suite to a throwaway database.

The smoke tests call `Base.metadata.drop_all()` between cases. Once DATABASE_URL
points at Supabase, running pytest with the app's real settings would drop the
hosted tables — so force a local URL before anything imports `app.database`,
which builds its engine at import time. An environment variable takes
precedence over the value in `.env`, which is what makes this stick.

Set TEST_DATABASE_URL to deliberately run the suite somewhere else — e.g. a
local Postgres container, to exercise the same backend Supabase runs:

    docker run -d --name settleflow-pg -e POSTGRES_PASSWORD=devpass \
        -e POSTGRES_DB=settleflow -p 55432:5432 postgres:16
    TEST_DATABASE_URL=postgresql://postgres:devpass@127.0.0.1:55432/settleflow \
        .venv/bin/pytest tests -q

Point that at a scratch database only. It gets dropped.
"""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "sqlite:///./test_settleflow.db"
)

from app.database import engine  # noqa: E402

if not os.environ.get("TEST_DATABASE_URL"):
    assert engine.url.get_backend_name() == "sqlite", (
        f"Tests must run against SQLite, got {engine.url.render_as_string(hide_password=True)}. "
        "Something imported app.database before conftest set DATABASE_URL."
    )
