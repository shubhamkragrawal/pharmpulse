-- Read-only role for the Streamlit app. Scoped to marts + metrics only --
-- no raw, no staging. Run via `make create-readonly-role` (envsubst
-- substitutes ${READONLY_PASSWORD} from .env before piping to psql --
-- psql itself does not expand ${VAR} shell syntax in a plain .sql file).
--
-- Not run automatically on container init: docker-entrypoint-initdb.d
-- scripts only execute on first volume creation (see decisions.md, M2), and
-- the pgdata volume already exists with data -- run this manually once.

CREATE ROLE pharmapulse_readonly LOGIN PASSWORD '${READONLY_PASSWORD}';
GRANT CONNECT ON DATABASE pharmapulse TO pharmapulse_readonly;
GRANT USAGE ON SCHEMA marts, metrics TO pharmapulse_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO pharmapulse_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA metrics TO pharmapulse_readonly;

-- Future dbt builds create new tables in these schemas -- without this, a
-- new mart/metric model would silently be invisible to the readonly role
-- until this script is re-run by hand.
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO pharmapulse_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA metrics GRANT SELECT ON TABLES TO pharmapulse_readonly;
