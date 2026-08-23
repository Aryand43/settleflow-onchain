"""Deploys the SettleFlow API to Modal as a long-running web service.

    modal deploy apps/api/modal_app.py

Modal is serverless by default: a container boots on the first request and is
torn down once it goes idle. Two knobs below pin that into a service that is
always up:

1. `min_containers=1` keeps one container warm permanently, so the API answers
   without a cold start.
2. `max_containers=2` caps the fan-out. State lives in Supabase, so this is not
   a correctness limit — it is a connection-budget one. database.py opens a
   pool of 5 with 5 overflow per container, so each container can hold 10
   Postgres connections, and Supabase's free-tier pooler will not absorb an
   unbounded number of those.

The Volume at /data holds only the email previews the app falls back to when
SMTP delivery fails. Modal runs background commits, so those persist without
the app calling `volume.commit()` itself.
"""

from pathlib import Path

import modal

API_DIR = Path(__file__).parent

# The one writable path: email previews, written when SMTP delivery fails.
# The database is Supabase, reached over the network via DATABASE_URL.
DATA_DIR = "/data"

image = (
    modal.Image.debian_slim(python_version="3.13")
    .pip_install_from_requirements(API_DIR / "requirements.txt")
    .env({"PYTHONUNBUFFERED": "1"})
    # add_local_dir mounts at runtime rather than baking a layer, so editing
    # app/ and redeploying skips the whole image rebuild.
    .add_local_dir(API_DIR / "app", remote_path="/root/app")
    .add_local_dir(API_DIR / "scripts", remote_path="/root/scripts")
)

volume = modal.Volume.from_name("settleflow-data", create_if_missing=True)

app = modal.App("settleflow-api", image=image)


def _persist_email_previews() -> None:
    """Redirects email_previews/ onto the Volume.

    `email.py` resolves PREVIEW_DIR relative to its own file, which lands on the
    container's ephemeral disk — so every preview written while SMTP is down
    would vanish with the container. Symlinking is the least invasive fix: no
    application code has to know it is running on Modal.
    """
    import os

    target = Path(DATA_DIR) / "email_previews"
    target.mkdir(parents=True, exist_ok=True)

    link = Path("/root/email_previews")
    if link.is_symlink() or link.exists():
        return
    os.symlink(target, link)


@app.function(
    volumes={DATA_DIR: volume},
    secrets=[modal.Secret.from_name("settleflow")],
    min_containers=1,
    max_containers=2,
    scaledown_window=1200,
    timeout=600,
)
@modal.concurrent(max_inputs=50)
@modal.asgi_app()
def fastapi_app():
    _persist_email_previews()

    # Imported inside the function, not at module scope: app.database builds the
    # SQLAlchemy engine at import time from get_settings(), and the Secret's
    # environment variables only exist once the container is running. Importing
    # this at the top of the file would bind the engine to the local .env during
    # deploy instead.
    from app.main import app as web_app

    return web_app


# --- Operational entrypoints -------------------------------------------------
# These target whatever DATABASE_URL points at, which is now hosted Supabase
# rather than a throwaway container file. `seed` is additive; `reset` destroys.


@app.function(secrets=[modal.Secret.from_name("settleflow")], timeout=600)
def seed():
    """modal run apps/api/modal_app.py::seed"""
    import sys

    sys.path.insert(0, "/root")
    from scripts.seed import seed as run_seed

    run_seed()


@app.function(secrets=[modal.Secret.from_name("settleflow")], timeout=600)
def reset():
    """Drops every table, then reseeds. modal run apps/api/modal_app.py::reset

    Destructive, and it reaches the same Supabase database the local Makefile
    targets do — there is no separate Modal copy to get this wrong against.
    """
    import sys

    sys.path.insert(0, "/root")
    from scripts.reset_db import reset as run_reset
    from scripts.seed import seed as run_seed

    run_reset()
    run_seed()
