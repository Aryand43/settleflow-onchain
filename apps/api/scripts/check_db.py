"""Verify DATABASE_URL actually connects, and report what's in it.

Run this right after pointing .env at Supabase — it separates "the connection
string is wrong" from "the app is broken", which is otherwise a confusing
failure to debug through a 500 in the dashboard.

    python scripts/check_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app.database import SessionLocal, engine


def main() -> int:
    print(f"URL     : {engine.url.render_as_string(hide_password=True)}")
    print(f"Driver  : {engine.dialect.driver}")

    version_sql = (
        "SELECT sqlite_version()"
        if engine.url.get_backend_name() == "sqlite"
        else "SELECT version()"
    )

    try:
        with engine.connect() as conn:
            version = conn.execute(text(version_sql)).scalar()
    except Exception as exc:
        print(f"\nFAILED to connect: {type(exc).__name__}: {exc}")
        print(
            "\nOn Supabase, check that you used the Session pooler host "
            "(port 5432) and URL-encoded any special characters in the password."
        )
        return 1

    print(f"Server  : {version}")

    tables = sorted(inspect(engine).get_table_names())
    if not tables:
        print("\nConnected, but no tables yet — run `python scripts/seed.py`.")
        return 0

    print(f"Tables  : {', '.join(tables)}")

    db = SessionLocal()
    try:
        for table in ("customers", "invoices", "activity_events", "negotiation_messages"):
            if table in tables:
                count = db.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                print(f"  {table:<22} {count} row(s)")

        if "invoice_counters" in tables:
            nxt = db.execute(text("SELECT next_value FROM invoice_counters WHERE id = 1")).scalar()
            print(f"\nNext invoice number: INV-{nxt:04d}" if nxt else "\nCounter row missing.")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
