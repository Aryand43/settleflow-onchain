"""Drops every table in the target database, then leaves it empty for seed.py.

Deliberately reflection-based rather than `Base.metadata.drop_all`. drop_all
only drops the tables the *running code* declares, so a container image built
before a model was added silently skips that table — and on Postgres the
leftover foreign key then blocks the parent drop:

    cannot drop table invoices because other objects depend on it
    DETAIL: constraint invoice_audit_events_invoice_id_fkey ...

Reflecting asks the database what is actually there, so a stale image or a
table added by hand can't wedge the reset. On Postgres one CASCADE statement
drops the lot, which also removes ordering from the equation.

This resets whatever DATABASE_URL points at — including hosted Supabase. That
is intended; the target is printed (credentials masked) so it is never a
surprise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from sqlalchemy import inspect, text

# Same as seed.py: this runs as a script, not a module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine  # noqa: E402


def _masked(url: object) -> str:
    return re.sub(r"://[^@]*@", "://***:***@", str(url))


def reset() -> None:
    backend = engine.url.get_backend_name()
    print(f"Resetting {backend}: {_masked(engine.url)}")

    tables = inspect(engine).get_table_names()
    if not tables:
        print("  nothing to drop — database is already empty")
        return

    print(f"  dropping {len(tables)} table(s): {', '.join(sorted(tables))}")
    with engine.begin() as conn:
        if backend == "postgresql":
            # One statement: CASCADE clears the foreign keys, so drop order
            # and unknown dependents both stop mattering.
            quoted = ", ".join(f'"{t}"' for t in sorted(tables))
            conn.execute(text(f"DROP TABLE IF EXISTS {quoted} CASCADE"))
        else:
            # SQLite has no CASCADE for DROP TABLE; disable FK enforcement for
            # the duration instead, which is equivalent here since every table
            # is going away.
            conn.execute(text("PRAGMA foreign_keys = OFF"))
            for t in sorted(tables):
                conn.execute(text(f'DROP TABLE IF EXISTS "{t}"'))
            conn.execute(text("PRAGMA foreign_keys = ON"))

    remaining = inspect(engine).get_table_names()
    if remaining:
        print(f"  ERROR: {len(remaining)} table(s) survived: {', '.join(sorted(remaining))}")
        sys.exit(1)
    print("  done — database is empty")


if __name__ == "__main__":
    reset()
