"""Exports one CSV per Streamlit dashboard to data/tableau_extracts/, for
manually building the Tableau Public dashboard (M5 Part 3). Connects via the
same read-only role Streamlit uses (marts + metrics only). Regenerate with
`make tableau-extracts` after any dbt build.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "tableau_extracts"

SPONSOR_CLASS_LABELS = {
    "INDUSTRY": "Industry",
    "NIH": "NIH",
    "FED": "Federal",
    "OTHER_GOV": "Other Government",
    "NETWORK": "Network",
    "INDIV": "Individual",
    "AMBIG": "Ambiguous",
    "OTHER": "Other",
    "UNKNOWN": "Unknown",
}

PHASE_LABELS = {
    "EARLY_PHASE1": "Early Phase 1",
    "PHASE1": "Phase 1",
    "PHASE2": "Phase 2",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
    "NA": "N/A",
}


def decode_sponsor_class(series: pd.Series) -> pd.Series:
    return series.map(lambda v: SPONSOR_CLASS_LABELS.get(v, v) if pd.notna(v) else "Unknown")


def decode_phase(series: pd.Series) -> pd.Series:
    def decode_one(value):
        if pd.isna(value) or value is None:
            return "Not Reported"
        return " / ".join(PHASE_LABELS.get(p, p) for p in str(value).split("|"))

    return series.map(decode_one)


def build_dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5433")
    db = os.environ["POSTGRES_DB"]
    user = os.environ.get("READONLY_USER", "pharmapulse_readonly")
    password = os.environ["READONLY_PASSWORD"]
    return f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=prefer"


def run_query(conn: psycopg.Connection, sql: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def export_approval_landscape(conn) -> pd.DataFrame:
    sql = """
        with applications as (
            select
                application_number,
                sponsor_name,
                bool_or(submission_status = 'AP') as is_approved,
                min(approval_date) filter (where submission_status = 'AP') as first_approval_date
            from marts.fct_approvals
            group by application_number, sponsor_name
        )
        select
            extract(year from first_approval_date)::int as approval_year,
            coalesce(sponsor_name, 'Unknown') as applicant_name,
            count(*) as approval_count
        from applications
        where is_approved and first_approval_date is not null
        group by 1, 2
        order by 1, 3 desc
    """
    return run_query(conn, sql)


def export_phase_funnel(conn) -> pd.DataFrame:
    sql = """
        select
            condition_name,
            avg(multi_condition_flag::int) as multi_condition_flag_rate,
            avg(matched_to_fda::int) as matched_to_fda_rate,
            max(condition_phase2_trials) as phase2_trials,
            max(condition_phase3_trials) as phase3_trials,
            max(condition_approved_trials) as approved_trials,
            max(phase2_to_phase3_rate) as phase2_to_phase3_rate,
            max(phase3_to_approval_rate) as phase3_to_approval_rate,
            max(phase2_to_approval_rate) as phase2_to_approval_rate
        from metrics.metric_phase_transition
        where condition_name is not null
        group by condition_name
        order by phase2_trials desc
    """
    return run_query(conn, sql)


def export_sponsor_league_table(conn) -> pd.DataFrame:
    sql = """
        select sponsor_name, sponsor_class, trials_total, trials_completed, success_rate
        from marts.dim_sponsor
        order by trials_total desc
    """
    df = run_query(conn, sql)
    df["sponsor_class"] = decode_sponsor_class(df["sponsor_class"])
    return df


def export_duration_trends(conn) -> pd.DataFrame:
    sql = """
        select start_year, trial_count, p25_duration_days, median_duration_days,
               p75_duration_days, yoy_change_days, yoy_change_pct
        from metrics.metric_duration_trends
        order by start_year
    """
    return run_query(conn, sql)


def export_sponsor_cohorts(conn) -> pd.DataFrame:
    sql = """
        select cohort_year, activity_year, years_since_cohort, active_sponsor_count,
               cohort_launch_sponsor_count, survivorship_rate, cohort_sponsor_count,
               cohort_total_trials, cohort_total_completed, cohort_avg_success_rate
        from metrics.metric_sponsor_cohorts
        order by cohort_year, activity_year
    """
    return run_query(conn, sql)


def export_termination_reasons(conn) -> pd.DataFrame:
    sql = """
        select phase, sponsor_class, why_stopped, enrollment_count,
               start_date, completion_date, duration_days
        from marts.fct_trials t
        left join marts.dim_sponsor s using (sponsor_key)
        where t.is_terminated
    """
    df = run_query(conn, sql)
    df["phase"] = decode_phase(df["phase"])
    df["sponsor_class"] = decode_sponsor_class(df["sponsor_class"])
    df["why_stopped"] = df["why_stopped"].fillna("Not Reported")
    return df


def export_phase_distribution(conn) -> pd.DataFrame:
    sql = """
        select extract(year from start_date)::int as start_year, phase, count(*) as trial_count
        from marts.fct_trials
        where start_date is not null
        group by 1, 2
        order by 1, 2
    """
    df = run_query(conn, sql)
    df["phase"] = decode_phase(df["phase"])
    return df.groupby(["start_year", "phase"], as_index=False)["trial_count"].sum()


def export_pipeline_trust(conn) -> pd.DataFrame:
    phase_transition_sql = """
        select
            avg(multi_condition_flag::int) as multi_condition_flag_rate,
            avg(matched_to_fda::int) as matched_to_fda_rate,
            bool_and(grouping_by_condition_name) as grouping_by_condition_name
        from metrics.metric_phase_transition
    """
    condition_null_sql = "select avg((therapeutic_area is null)::int) as therapeutic_area_null_rate from marts.dim_condition"
    completion_null_sql = "select avg((completion_date is null)::int) as completion_date_null_rate from marts.fct_trials"

    pt = run_query(conn, phase_transition_sql)
    cond = run_query(conn, condition_null_sql)
    comp = run_query(conn, completion_null_sql)
    df = pd.concat([pt, cond, comp], axis=1)
    rate_cols = [c for c in df.columns if c.endswith("_rate")]
    df[rate_cols] = df[rate_cols].astype(float).round(4)
    return df


EXPORTS = {
    "approval_landscape.csv": export_approval_landscape,
    "phase_funnel.csv": export_phase_funnel,
    "sponsor_league_table.csv": export_sponsor_league_table,
    "duration_trends.csv": export_duration_trends,
    "sponsor_cohorts.csv": export_sponsor_cohorts,
    "termination_reasons.csv": export_termination_reasons,
    "phase_distribution.csv": export_phase_distribution,
    "pipeline_trust.csv": export_pipeline_trust,
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = psycopg.connect(build_dsn())
    try:
        for filename, export_fn in EXPORTS.items():
            df = export_fn(conn)
            path = OUTPUT_DIR / filename
            df.to_csv(path, index=False)
            print(f"wrote {path} ({len(df):,} rows)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
