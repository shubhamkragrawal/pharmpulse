.PHONY: start stop extract test create-readonly-role tableau-extracts streamlit

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

# One-time setup (or after ${READONLY_PASSWORD} changes): creates the
# read-only role Streamlit connects with. Not run automatically on container
# init -- see streamlit/scripts/create_readonly_role.sql for why.
create-readonly-role:
	set -a; . ./.env; set +a; \
	envsubst < streamlit/scripts/create_readonly_role.sql | \
	PGPASSWORD=$$POSTGRES_PASSWORD psql -h $${POSTGRES_HOST:-localhost} -p $${POSTGRES_PORT:-5433} -U $$POSTGRES_USER -d $$POSTGRES_DB

tableau-extracts:
	uv run python scripts/export_tableau_extracts.py

streamlit:
	uv run streamlit run streamlit/app.py
