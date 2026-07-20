# M7 proof artifact: kill/retry and failure-callback verification

This is the exact command sequence used to prove two things the spec
requires: "a killed mid-run task demonstrably auto-retries," and a
`dbt_test` failure fires the failure callback and blocks `notify`. Run these
against a running `make airflow-up` stack. Same pattern already used and
verified for the extraction layer in M1 (`decisions.md`, "`uv run
<script>` is not a safe target for `kill -9`...") — same idea, now proven
at the Airflow task-process level instead of the bare extractor-script level.

## Prerequisites

```bash
make start          # postgres up
make airflow-init    # one-shot: creates the airflow DB, admin user
make airflow-up       # webserver (localhost:8080) + scheduler
```

## 1. Trigger the DAG manually

```bash
docker compose exec airflow-scheduler airflow dags trigger pharmapulse_daily
```

Note the run's logical date (or just use `latest` in the commands below —
`airflow tasks states-for-dag-run` accepts either):

```bash
docker compose exec airflow-scheduler \
  airflow dags list-runs -d pharmapulse_daily --state running
```

Copy the `run_id` printed there into `$RUN_ID` for the commands below:

```bash
export RUN_ID="<paste run_id here>"
```

## 2. Kill the `extract_ctgov` task mid-run

`extract_ctgov` pulls ~594K CT.gov trials at `page_size=1000` (~600 pages),
so there's a multi-minute window to catch it mid-run. With
`LocalExecutor`, each running task is a real OS subprocess of the scheduler
container — find its PID and kill it directly (same technique the M1
decision entry already established: `kill -9` on the task PID, not on a
wrapper process):

```bash
docker compose exec airflow-scheduler bash -c \
  "ps aux | grep '[t]ask_type LocalTaskJob.*extract_ctgov'"
```

That line's second column is the PID. Kill it:

```bash
docker compose exec airflow-scheduler bash -c \
  "kill -9 \$(ps aux | grep '[t]ask_type LocalTaskJob.*extract_ctgov' | awk '{print \$2}')"
```

## 3. Watch it auto-retry

```bash
make airflow-logs
```

Look for the sequence, in order:
- `extract_ctgov` task instance moves to `up_for_retry` (the killed
  process is picked up by the scheduler's heartbeat as a failure, since
  `retries=2` and `retry_delay=timedelta(minutes=5)` with
  `retry_exponential_backoff=True` are set in the DAG's `default_args`)
- After the backoff delay, a second `LocalTaskJob` log line for
  `extract_ctgov` with `try_number=2`
- `extract_ctgov` reaches `success` on the retry

You can also poll task state directly instead of reading logs:

```bash
watch -n 5 "docker compose exec airflow-scheduler \
  airflow tasks states-for-dag-run pharmapulse_daily $RUN_ID"
```

## 4. Confirm the retry succeeded and the DAG continued downstream

```bash
docker compose exec airflow-scheduler \
  airflow tasks states-for-dag-run pharmapulse_daily $RUN_ID
```

Expected: `extract_ctgov` shows `success` (not `failed`), and
`extract_fda` / `load_raw` subsequently move from `none` → `running` →
`success` on their own, proving the DAG resumed downstream after the
kill+retry rather than staying stuck.

The extraction itself is also idempotent on top of the retry: because
`CTGovExtractor` checkpoints per page to `raw.extraction_checkpoints`
(`core/extractor_base.py`), the retried attempt resumes from
`last_page_completed + 1` instead of re-fetching pages the killed attempt
already upserted — this is the same checkpoint-resume behavior verified
live in M1, now exercised through Airflow's retry mechanism instead of a
manually re-run script.

## 5. Trigger a `dbt_test` failure and confirm the callback fires

Temporarily add a singular dbt test that always fails (a singular test
"fails" if its query returns any rows):

```bash
mkdir -p dbt/tests
cat > dbt/tests/force_failure.sql <<'EOF'
-- TEMPORARY: proves dbt_test failure -> on_failure_callback -> notify blocked.
-- Delete this file after the proof run.
select 1 as forced_failure
EOF
```

Trigger a fresh run:

```bash
docker compose exec airflow-scheduler airflow dags trigger pharmapulse_daily
```

Watch the scheduler logs for the failure callback's stub output:

```bash
make airflow-logs | grep "ALERT: would send Slack notification"
```

Expected: the `ALERT:` line from `failure_callback` in
`airflow/dags/pharmapulse_daily.py` appears, naming `task_id=dbt_test`,
once `dbt_test` exhausts its 2 retries and is marked `failed`. Confirm
`notify` never ran:

```bash
docker compose exec airflow-scheduler \
  airflow tasks states-for-dag-run pharmapulse_daily <new run_id>
```

Expected: `dbt_test` = `failed`, `notify` = `upstream_failed` (never
executed) — proving the failure blocks downstream as required.

**Clean up** — remove the forced-failure test before any real run:

```bash
rm dbt/tests/force_failure.sql
```
