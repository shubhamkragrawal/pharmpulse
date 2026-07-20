"""Creates the `airflow` metadata database on the shared Postgres instance,
idempotently. Run once by the airflow-init service before `airflow db init`.

Not a docker-entrypoint-initdb.d script: those only run on first volume
creation (already learned the hard way for ops.extraction_log and the
readonly role -- see decisions.md), and this repo's `pgdata` volume already
existed before Airflow was added. Checking-then-creating here works whether
the volume is fresh or pre-existing.
"""
from __future__ import annotations

import os

import psycopg2
from psycopg2 import sql

DB_NAME = "airflow"


def main() -> None:
    conn = psycopg2.connect(
        host="postgres",
        port=5432,
        dbname="postgres",
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            if cur.fetchone():
                print(f"database '{DB_NAME}' already exists, skipping")
                return
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
            print(f"created database '{DB_NAME}'")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
