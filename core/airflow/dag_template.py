from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from core.config import get_active_domain, get_domain_config
from core.extraction_runner import run_extraction

ACTIVE_DOMAIN = get_active_domain()
DOMAIN_CONFIG = get_domain_config(ACTIVE_DOMAIN)


def _extract_source(source_name: str) -> None:
    run_extraction(domain=ACTIVE_DOMAIN, sources=[source_name])


with DAG(
    dag_id=f"{ACTIVE_DOMAIN}_daily",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args={"retries": 2},
) as dag:
    extract_tasks = [
        PythonOperator(
            task_id=f"extract_{source_name}",
            python_callable=_extract_source,
            op_kwargs={"source_name": source_name},
        )
        for source_name in DOMAIN_CONFIG["extraction"]
    ]

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd dbt && ACTIVE_DOMAIN={ACTIVE_DOMAIN} dbt build",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd dbt && ACTIVE_DOMAIN={ACTIVE_DOMAIN} dbt test",
    )

    extract_tasks >> dbt_build >> dbt_test
