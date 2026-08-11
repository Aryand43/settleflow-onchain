.PHONY: dev seed test test-api test-contracts install

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
