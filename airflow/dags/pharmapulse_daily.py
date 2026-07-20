"""pharmapulse_daily -- one production-grade DAG, per 04_PHARMAPULSE_SPEC.md M7.

extract_ctgov >> extract_fda >> load_raw >> dbt_build >> dbt_test >> notify

Deliberately one well-built DAG, not five toy DAGs (spec's explicit call).
Runs inside the airflow-webserver/airflow-scheduler containers, which mount
the whole repo at /opt/airflow/pharmpulse (see docker-compose.yml) so
`core.*` / `domains.pharma.*` import the same way they do for `make extract`.
"""
from __future__ import annotations

import logging
from datetime import timedelta, datetime,timezone

import psycopg
from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from core.extraction_runner import build_dsn
from domains.pharma.extractors import CTGovExtractor, OpenFDAExtractor

logger = logging.getLogger(__name__)

DBT_PROJECT_DIR = "/opt/airflow/pharmpulse/dbt"
DBT_PROFILES_DIR = "/opt/airflow/dbt_profiles"


def failure_callback(context: dict) -> None:
    """Fires on any task failure or retry exhaustion (wired via default_args.
    on_failure_callback, so every task in the DAG inherits it -- this is what
    fires when dbt_test fails, not just extraction tasks).

    TODO: replace this stub with a real Slack notification. Read the webhook
    URL from the SLACK_WEBHOOK_URL env var (not set anywhere yet) and POST
    the message body below to it.
    """
    task_instance = context["task_instance"]
    logger.error(
        "ALERT: would send Slack notification here. "
        "dag_id=%s task_id=%s logical_date=%s exception=%s",
        context["dag"].dag_id,
        task_instance.task_id,
        context.get("logical_date", context.get("execution_date")),
        context.get("exception"),
    )


def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis) -> None:
    """Fires when a task with `sla=` set (dbt_test, below) doesn't finish
    within its SLA window relative to the DAG run's start. Separate from
    failure_callback because Airflow gives SLA misses a different callback
    signature (dag/task_list/slas, not a single `context` dict) -- this is
    not a duplicate, it's the API's actual shape for this event.

    TODO: same Slack wiring as failure_callback, via SLACK_WEBHOOK_URL.
    """
    logger.error(
        "ALERT: would send Slack notification here. "
        "SLA missed. dag_id=%s tasks=%s slas=%s",
        dag.dag_id,
        [t.task_id for t in task_list],
        slas,
    )


def _already_extracted_for_run(conn: psycopg.Connection, source_name: str, logical_date) -> bool:
    """Idempotency check on execution_date.

    raw.extraction_checkpoints is source-keyed (one row per 'ctgov'/'openfda'
    tracking lifetime resume state), not run-keyed -- it has no
    execution_date column (see core/extractor_base.py). There's no schema
    to add an execution_date column to without a migration this milestone
    doesn't otherwise need, so "already done for this execution_date" is
    approximated as: status = 'completed' AND last_run_completed_at falls on
    the same calendar date as this DAG run's logical_date. Documented as an
    as-built deviation in 04_PHARMAPULSE_SPEC.md's M7 entry.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, last_run_completed_at FROM raw.extraction_checkpoints WHERE source = %s",
            (source_name,),
        )
        row = cur.fetchone()
    if row is None:
        return False
    status, completed_at = row
    if status != "completed" or completed_at is None:
        return False
    return completed_at.date() == logical_date.date()


def extract_ctgov(**context) -> None:
    logical_date = context["logical_date"]
    dsn = build_dsn()
    with psycopg.connect(dsn) as conn:
        if _already_extracted_for_run(conn, "ctgov", logical_date):
            logger.info("ctgov already extracted for %s, skipping", logical_date.date())
            return
    extractor = CTGovExtractor(db_dsn=dsn, page_size=1000)
    total = extractor.run()
    logger.info("ctgov extraction upserted %d records", total)


def extract_fda(**context) -> None:
    logical_date = context["logical_date"]
    dsn = build_dsn()
    with psycopg.connect(dsn) as conn:
        if _already_extracted_for_run(conn, "openfda", logical_date):
            logger.info("openfda already extracted for %s, skipping", logical_date.date())
            return
    extractor = OpenFDAExtractor(db_dsn=dsn, page_size=100)
    total = extractor.run()
    logger.info("openfda extraction upserted %d records", total)


def load_raw_gate(**context) -> None:
    """Validation gate, not a load step -- extraction already writes to raw
    directly. Fails loudly if either raw table is empty, instead of letting
    dbt_build silently run against nothing."""
    dsn = build_dsn()
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM raw.ct_studies")
        ct_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM raw.fda_applications")
        fda_count = cur.fetchone()[0]
    logger.info("raw.ct_studies=%d raw.fda_applications=%d", ct_count, fda_count)
    if ct_count == 0 or fda_count == 0:
        raise AirflowException(
            f"raw row count gate failed: ct_studies={ct_count}, fda_applications={fda_count}"
        )


def notify(**context) -> None:
    """TODO: replace with a real Slack notification. Read the webhook URL
    from the SLACK_WEBHOOK_URL env var (not set anywhere yet)."""
    logical_date = context["logical_date"]
    logger.info("pharmapulse_daily completed successfully for %s", logical_date)


default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": False,
    "on_failure_callback": failure_callback,
}

with DAG(
    dag_id="pharmapulse_monthly",
    schedule="@monthly",
    start_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    sla_miss_callback=sla_miss_callback,
) as dag:
    extract_ctgov_task = PythonOperator(
        task_id="extract_ctgov",
        python_callable=extract_ctgov,
    )

    extract_fda_task = PythonOperator(
        task_id="extract_fda",
        python_callable=extract_fda,
    )

    load_raw_task = PythonOperator(
        task_id="load_raw",
        python_callable=load_raw_gate,
    )

    dbt_build_task = BashOperator(
        task_id="dbt_build",
        bash_command=(
            f"dbt build --project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} --no-version-check"
        ),
    )

    dbt_test_task = BashOperator(
        task_id="dbt_test",
        bash_command=f"dbt test --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}",
        sla=timedelta(hours=6),
    )

    notify_task = PythonOperator(
        task_id="notify",
        python_callable=notify,
    )

    extract_ctgov_task >> extract_fda_task >> load_raw_task >> dbt_build_task >> dbt_test_task >> notify_task
