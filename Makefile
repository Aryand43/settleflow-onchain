.PHONY: dev seed test test-api test-contracts install \
        up down logs docker-seed docker-reset reset-all chain-up chain-deploy demo preflight

# --- Running locally (needs Python + Node installed) ---

dev:
	cd apps/api && .venv/bin/uvicorn app.main:app --reload --port 8000 &
	cd apps/web && npm run dev

seed:
	cd apps/api && .venv/bin/python scripts/seed.py

test-api:
	cd apps/api && .venv/bin/pytest tests -v

test-contracts:
	cd contracts && forge test -vv

test: test-api

install:
	cd apps/api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd apps/web && npm install

# --- Running in Docker (needs only Docker) ---

up:
	docker compose up --build -d
	@echo "API  http://localhost:8000"
	@echo "Web  http://localhost:3000"
	@echo "Run 'make docker-seed' if this is a fresh database."

down:
	docker compose --profile chain down

logs:
	docker compose logs -f

docker-seed:
	docker compose run --rm api python scripts/seed.py

# Drops every table and reseeds. Whatever DATABASE_URL points at — including
# Supabase — so read it twice before running it.
#
# DEMO_CUSTOMER_EMAIL points all three seeded customers at one inbox using
# +tags, so reminder emails actually arrive somewhere you can open on camera.
# Without it they keep @example.com addresses, which bounce.
DEMO_CUSTOMER_EMAIL ?= settleflowhackathon@gmail.com

docker-reset:
	docker compose run --rm api python -c "\
	from app.database import Base, engine; import app.models; Base.metadata.drop_all(bind=engine)"
	docker compose run --rm -e DEMO_CUSTOMER_EMAIL=$(DEMO_CUSTOMER_EMAIL) api python scripts/seed.py
	@$(MAKE) preflight

# Resets the database AND the chain together. Use this between takes when the
# chain is running.
#
# On-chain invoice ids are derived from owner + invoice number, so a reseeded
# INV-0001 lands on the same id as the old one. Reset only the database and the
# router still remembers the previous INV-0001 as paid — the new one then looks
# settled before anyone has paid it.
reset-all:
	docker compose --profile chain restart anvil
	@sleep 5
	docker compose --profile chain run --rm contracts
	docker compose up -d api
	@sleep 10
	@$(MAKE) docker-reset

# --- Local chain, for the on-chain settlement demo ---

chain-up:
	docker compose --profile chain up -d anvil

chain-deploy:
	docker compose --profile chain run --rm contracts
	@echo "Copy the two addresses above into .env, then: docker compose up -d api"

# --- One command to bring the whole demo up, chain included ---

demo: chain-up chain-deploy
	docker compose up -d --build
	@echo
	@echo "Waiting for the API to come up..."
	@sleep 15
	@$(MAKE) preflight

# Everything that has to be true before you hit record.
preflight:
	@echo "PRE-FLIGHT"
	@printf "  chain configured : "; curl -s http://localhost:8000/api/invoices/by-token/demo-pending-token/payment-page \
	  | python3 -c "import json,sys; print(json.load(sys.stdin)['chain_configured'])" 2>/dev/null || echo "API not up yet"
	@printf "  email delivery   : "; curl -s -H "X-API-Key: dev-key" http://localhost:8000/api/email/status \
	  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['configured'], d['from_address'] or '')" 2>/dev/null || echo "?"
	@printf "  chat (LLM key)   : "; curl -s -H "X-API-Key: dev-key" http://localhost:8000/api/chat/status \
	  | python3 -c "import json,sys; print(json.load(sys.stdin)['configured'])" 2>/dev/null || echo "?"
	@printf "  invoices in db   : "; curl -s -H "X-API-Key: dev-key" http://localhost:8000/api/invoices \
	  | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?"
	@echo
	@echo "  Web  http://localhost:3000   sign in: demo@settleflow.app / settleflow"
