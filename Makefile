.PHONY: dev seed test test-api test-contracts install \
        modal-secret modal-deploy modal-status modal-reset-db modal-reset-all \
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

# Rebuilds first, deliberately. `up -d api` reuses whatever image is cached,
# and a reset driven by an image older than the current models drops only the
# tables that image declares — leaving the rest behind with foreign keys that
# block the parent drop. Resetting against a schema the code no longer matches
# is how this target failed before; the rebuild is the cheap way to stop it.
docker-reset:
	docker compose build api
	docker compose run --rm api python scripts/reset_db.py
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
	docker compose up -d --build api
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

# --- Modal (hosted demo) -----------------------------------------------------
#
# Two Modal Apps: the API and the Anvil chain it settles against. Both keep one
# container warm permanently, so they do not scale to zero between takes.

MODAL_RPC ?= https://vyoj--settleflow-anvil-anvil.us-east.modal.direct
MODAL_API ?= https://vyoj--settleflow-api-fastapi-app.modal.run

# Rebuilds the hosted Secret from apps/api/.env, with the handful of values that
# differ between local and hosted overridden (see the script). Run after changing
# any key in .env, then redeploy.
modal-secret:
	python3 scripts/sync_modal_secret.py

modal-deploy:
	modal deploy apps/api/modal_anvil.py
	modal deploy apps/api/modal_app.py

modal-status:
	@modal app list --json | python3 -c "import json,sys; \
	  rows=[a for a in json.load(sys.stdin) if a['description'].startswith('settleflow') and a['state']=='deployed']; \
	  [print('  %-22s %-10s tasks=%s' % (a['description'], a['state'], a['tasks'])) for a in rows] or print('  no deployed apps')"
	@printf "  api   : "; curl -s $(MODAL_API)/api/health || echo "DOWN"
	@printf "\n  chain : "; curl -s -X POST $(MODAL_RPC) -H 'Content-Type: application/json' \
	  -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' || echo "DOWN"
	@echo

# Resets the hosted database only. Use modal-reset-all between takes instead —
# on its own this leaves the chain remembering invoices the database forgot.
modal-reset-db:
	modal run apps/api/modal_app.py::reset

# Wipes the chain AND the database together, then redeploys the contracts.
#
# These two must be reset as a pair. On-chain invoice ids are sha256(owner:number),
# so a reseeded INV-0004 lands on the id the old INV-0004 used. Reset only the
# database and the router still reports that id as paid — the new invoice then
# looks settled before anyone has paid it.
#
# The wait loop is not optional. `modal app stop` returns before the container
# is gone, and Anvil dumps its state on SIGTERM — deleting the state file while
# that is still pending loses the race, the old chain reloads, and the contracts
# redeploy to *different* addresses because the deployer nonce carried over.
#
# Contract addresses are deterministic (CREATE = deployer + nonce), so a truly
# fresh chain reproduces the same two addresses and the Modal Secret needs no
# change. If the addresses printed below differ, the chain was not actually
# empty — rerun this target.
modal-reset-all:
	modal app stop settleflow-anvil --yes
	@echo "waiting for the Anvil container to terminate..."
	@until [ "$$(modal app list --json 2>/dev/null | python3 -c "import json,sys; print(sum(int(a['tasks']) for a in json.load(sys.stdin) if a['description']=='settleflow-anvil' and a['state']=='deployed'))")" = "0" ]; do sleep 5; done
	modal volume rm settleflow-chain anvil-state.json || true
	modal deploy apps/api/modal_anvil.py
	@echo "waiting for the chain to accept requests..."
	@until curl -s -X POST $(MODAL_RPC) -H 'Content-Type: application/json' \
	  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' | grep -q result; do sleep 3; done
	modal run apps/api/modal_anvil.py::deploy_contracts --rpc-url $(MODAL_RPC)
	@$(MAKE) modal-reset-db
	@$(MAKE) modal-status
