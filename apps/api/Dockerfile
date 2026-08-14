# SettleFlow API — FastAPI + SQLAlchemy
#
# Build from the repo root so the context includes nothing from apps/web:
#   docker build -f apps/api/Dockerfile -t settleflow-api apps/api

FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Requirements first: this layer only rebuilds when dependencies change, not on
# every source edit.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY pytest.ini ./
COPY tests ./tests

# SQLite and the email previews need somewhere writable that survives a
# container restart — compose mounts a volume here.
RUN mkdir -p /app/data /app/email_previews

# Runs unprivileged: nothing in here needs root, and a container that can't
# write to its own image is one fewer way for a bad day to get worse.
RUN useradd --create-home --uid 10001 settleflow \
    && chown -R settleflow:settleflow /app
USER settleflow

EXPOSE 8000

# Compose overrides the DB URL; this default keeps a bare `docker run` working
# without any environment at all.
ENV DATABASE_URL=sqlite:////app/data/settleflow.db

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
