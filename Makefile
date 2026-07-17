.PHONY: start stop extract test

start:
	docker compose up -d
	@echo "waiting for postgres to be healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' pharmapulse_postgres 2>/dev/null)" = "healthy" ]; do sleep 1; done
	@echo "postgres is up."

stop:
	docker compose down

extract:
	uv run python main.py extract

test:
	uv run pytest tests/ -v
