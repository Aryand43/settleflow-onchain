from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()


def _normalize_url(url: str) -> str:
    """Supabase hands out connection strings as `postgresql://...`, which
    SQLAlchemy resolves to the psycopg2 driver. We ship psycopg 3, so point the
    URL at that dialect explicitly and let the pasted string work as-is."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


database_url = _normalize_url(settings.database_url)
is_sqlite = database_url.startswith("sqlite")

if is_sqlite:
    connect_args = {"check_same_thread": False}
    engine_kwargs = {}
else:
    connect_args = {
        # Safe against both Supabase poolers: pgbouncer in transaction mode
        # rejects the server-side prepared statements psycopg 3 creates by
        # default. Disabling them costs a little planning time and nothing else.
        "prepare_threshold": None,
    }
    engine_kwargs = {
        # A hosted DB drops idle connections; without pre_ping the first query
        # after an idle period fails instead of transparently reconnecting.
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 5,
    }

engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import activity, customer, invoice, negotiation, user  # noqa: F401

    Base.metadata.create_all(bind=engine)
