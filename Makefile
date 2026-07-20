.PHONY: start stop extract test create-readonly-role tableau-extracts streamlit airflow-init airflow-up airflow-down airflow-logs trigger-dag

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

# Orchestration (M7). airflow-init is one-shot (creates the airflow metadata
# DB, runs migrations, creates the admin user) -- run it once, or again after
# a fresh volume/`docker compose down -v`. --wait blocks until it exits.
airflow-init:
	docker compose up airflow-init --wait

airflow-up:
	docker compose up airflow-webserver airflow-scheduler -d

airflow-down:
	docker compose stop airflow-webserver airflow-scheduler

airflow-logs:
	docker compose logs -f airflow-scheduler

trigger-dag:
	docker compose exec airflow-scheduler airflow dags trigger pharmapulse_daily
