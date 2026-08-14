.PHONY: dev seed test test-api test-contracts install \
        up down logs docker-seed docker-reset chain-up chain-deploy

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
docker-reset:
	docker compose run --rm api python -c "\
	from app.database import Base, engine; import app.models; Base.metadata.drop_all(bind=engine)"
	docker compose run --rm api python scripts/seed.py

# --- Local chain, for the on-chain settlement demo ---

chain-up:
	docker compose --profile chain up -d anvil

chain-deploy:
	docker compose --profile chain run --rm contracts
	@echo "Copy the two addresses above into .env, then: docker compose up -d api"
