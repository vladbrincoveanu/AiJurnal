export $(shell sed 's/=.*//' .env 2>/dev/null)

.PHONY: up migrate frontend-install

up:
	docker compose up --build

migrate:
	docker compose run --rm backend alembic upgrade head

frontend-install:
	cd frontend && npm install
