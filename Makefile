.PHONY: backend-install frontend-install migrate seed api web test lint

backend-install:
	cd server && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt

frontend-install:
	cd client && npm install

migrate:
	cd server && .venv/bin/alembic upgrade head

seed:
	cd server && .venv/bin/python -m app.scripts.seed_data

api:
	cd server && .venv/bin/uvicorn app.main:app --reload --port 8000

web:
	cd client && npm run dev

test:
	cd server && .venv/bin/pytest -q
	cd client && npm run typecheck

lint:
	cd server && .venv/bin/ruff check app tests
	cd server && .venv/bin/ruff format --check app tests
	cd client && npm run lint
