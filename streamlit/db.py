"""Read-only query layer. All SQL lives here, not in page render logic.

Connects via the pharmapulse_readonly role (marts + metrics schemas only,
no raw/staging access) -- see scripts/create_readonly_role.sql and the
access-control disclosure in README.md.
"""

import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _build_readonly_dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5433")
    db = os.environ["POSTGRES_DB"]
    user = os.environ.get("READONLY_USER", "pharmapulse_readonly")
    password = os.environ["READONLY_PASSWORD"]
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@st.cache_resource
def get_connection() -> psycopg.Connection:
    return psycopg.connect(_build_readonly_dsn())


@st.cache_data(ttl=3600)
def run_query(sql: str) -> pd.DataFrame:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


# ─── Dashboard 1: Approval Landscape ────────────────────────────────────────

@st.cache_data(ttl=3600)
def approvals_by_sponsor_class_year() -> pd.DataFrame:
    # aggregate up from submission-event grain (application_number,
    # submission_type, submission_number) to one row per application before
    # counting "an approval" -- fct_approvals is NOT application-level.
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
            coalesce(sponsor_name, 'UNKNOWN') as sponsor_name,
            count(*) as approval_count
        from applications
        where is_approved and first_approval_date is not null
        group by 1, 2
        order by 1
    """
    return run_query(sql)


@st.cache_data(ttl=3600)
def top_sponsors_by_approval_count(limit: int = 20) -> pd.DataFrame:
    sql = f"""
        with applications as (
            select
                application_number,
                sponsor_name,
                bool_or(submission_status = 'AP') as is_approved
            from marts.fct_approvals
            group by application_number, sponsor_name
        )
        select
            coalesce(sponsor_name, 'UNKNOWN') as sponsor_name,
            count(*) as approval_count
        from applications
        where is_approved
        group by 1
        order by 2 desc
        limit {limit}
    """
    return run_query(sql)


# ─── Dashboard 2: Phase Funnel ──────────────────────────────────────────────

@st.cache_data(ttl=3600)
def phase_funnel_by_condition(min_phase2_trials: int = 50) -> pd.DataFrame:
    sql = f"""
        select distinct
            condition_name,
            condition_phase2_trials,
            condition_phase3_trials,
            condition_approved_trials,
            phase2_to_phase3_rate,
            phase3_to_approval_rate,
            phase2_to_approval_rate
        from metrics.metric_phase_transition
        where condition_phase2_trials >= {min_phase2_trials}
        order by condition_phase2_trials desc
    """
    return run_query(sql)


@st.cache_data(ttl=3600)
def phase_funnel_audit_metrics() -> pd.DataFrame:
    sql = """
        select
            avg(multi_condition_flag::int) as multi_condition_flag_rate,
            avg(matched_to_fda::int) as matched_to_fda_rate,
            count(*) as trial_count
        from metrics.metric_phase_transition
    """
    return run_query(sql)


# ─── Dashboard 3: Sponsor League Table ──────────────────────────────────────

@st.cache_data(ttl=3600)
def sponsor_league_table() -> pd.DataFrame:
    sql = """
        select
            sponsor_name,
            sponsor_class,
            trials_total,
            trials_completed,
            success_rate
        from marts.dim_sponsor
        order by trials_total desc
    """
    return run_query(sql)


# ─── Dashboard 4: Duration Trends ───────────────────────────────────────────

@st.cache_data(ttl=3600)
def duration_trends_overall() -> pd.DataFrame:
    sql = """
        select start_year, trial_count, p25_duration_days, median_duration_days,
               p75_duration_days, yoy_change_days, yoy_change_pct
        from metrics.metric_duration_trends
        order by start_year
    """
    return run_query(sql)


@st.cache_data(ttl=3600)
def duration_trends_by_phase() -> pd.DataFrame:
    sql = """
        select start_year, phase, trial_count, p25_duration_days,
               median_duration_days, p75_duration_days, yoy_change_days
        from metrics.metric_duration_trends_by_phase
        order by phase, start_year
    """
    return run_query(sql)


# ─── Dashboard 5: Sponsor Cohort Survivorship ───────────────────────────────

@st.cache_data(ttl=3600)
def sponsor_cohort_survivorship() -> pd.DataFrame:
    sql = """
        select cohort_year, activity_year, years_since_cohort,
               active_sponsor_count, cohort_launch_sponsor_count, survivorship_rate
        from metrics.metric_sponsor_cohorts
        order by cohort_year, activity_year
    """
    return run_query(sql)


# ─── Dashboard 6: Termination Reasons ───────────────────────────────────────

@st.cache_data(ttl=3600)
def termination_rate_by_phase() -> pd.DataFrame:
    sql = """
        select
            coalesce(phase, 'NOT REPORTED') as phase,
            count(*) as trial_count,
            count(*) filter (where is_terminated) as terminated_count,
            round(count(*) filter (where is_terminated)::numeric / count(*), 4) as termination_rate
        from marts.fct_trials
        group by 1
        order by termination_rate desc
    """
    return run_query(sql)


@st.cache_data(ttl=3600)
def termination_rate_by_sponsor_class() -> pd.DataFrame:
    sql = """
        select
            coalesce(s.sponsor_class, 'UNKNOWN') as sponsor_class,
            count(*) as trial_count,
            count(*) filter (where t.is_terminated) as terminated_count,
            round(count(*) filter (where t.is_terminated)::numeric / count(*), 4) as termination_rate
        from marts.fct_trials t
        left join marts.dim_sponsor s using (sponsor_key)
        group by 1
        order by termination_rate desc
    """
    return run_query(sql)


@st.cache_data(ttl=3600)
def why_stopped_breakdown(limit: int = 15) -> pd.DataFrame:
    sql = f"""
        select why_stopped, count(*) as trial_count
        from marts.fct_trials
        where why_stopped is not null
        group by 1
        order by 2 desc
        limit {limit}
    """
    return run_query(sql)


@st.cache_data(ttl=3600)
def why_stopped_coverage() -> pd.DataFrame:
    sql = """
        select
            count(*) filter (where is_terminated) as terminated_trials,
            count(*) filter (where is_terminated and why_stopped is not null) as terminated_with_reason
        from marts.fct_trials
    """
    return run_query(sql)


# ─── Dashboard 7: Phase Distribution Over Time ──────────────────────────────

@st.cache_data(ttl=3600)
def phase_distribution_by_year() -> pd.DataFrame:
    sql = """
        select
            extract(year from start_date)::int as start_year,
            coalesce(phase, 'NOT REPORTED') as phase,
            count(*) as trial_count
        from marts.fct_trials
        where start_date is not null
        group by 1, 2
        order by 1, 2
    """
    return run_query(sql)


# ─── Dashboard 8: Pipeline Trust ────────────────────────────────────────────

@st.cache_data(ttl=3600)
def pipeline_trust_scorecard() -> dict:
    phase_transition_sql = """
        select
            avg(multi_condition_flag::int) as multi_condition_flag_rate,
            avg(matched_to_fda::int) as matched_to_fda_rate,
            bool_and(grouping_by_condition_name) as grouping_by_condition_name
        from metrics.metric_phase_transition
    """
    condition_null_sql = """
        select avg((therapeutic_area is null)::int) as therapeutic_area_null_rate
        from marts.dim_condition
    """
    completion_null_sql = """
        select avg((completion_date is null)::int) as completion_date_null_rate
        from marts.fct_trials
    """
    pt = run_query(phase_transition_sql).iloc[0]
    cond = run_query(condition_null_sql).iloc[0]
    comp = run_query(completion_null_sql).iloc[0]
    return {
        "multi_condition_flag_rate": float(pt["multi_condition_flag_rate"]),
        "matched_to_fda_rate": float(pt["matched_to_fda_rate"]),
        "grouping_by_condition_name": bool(pt["grouping_by_condition_name"]),
        "therapeutic_area_null_rate": float(cond["therapeutic_area_null_rate"]),
        "completion_date_null_rate": float(comp["completion_date_null_rate"]),
    }
