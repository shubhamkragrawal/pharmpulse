-- GRAIN: one row per (cohort_year, activity_year). cohort_year = the year of
-- a sponsor's earliest fct_trials.start_date; sponsors with an all-NULL
-- start_date across every trial are excluded from cohorting (can't assign a
-- cohort year), not silently dropped from the source data itself.
--
-- ACTIVE-YEAR DEFINITION: a trial with a NULL completion_date is treated as
-- active only in its start year, not open-ended/"still active" through the
-- present. See decisions.md -- the alternative (treat as ongoing) would
-- inflate survivorship in later years for any trial with an unknown end date.
--
-- trials_total/trials_completed/success_rate are reused directly from
-- dim_sponsor (M3), aggregated (SUM/AVG) to cohort_year -- not recomputed
-- from fct_trials.

with sponsor_first_year as (

    select
        dim_sponsor.sponsor_key,
        dim_sponsor.sponsor_name,
        dim_sponsor.trials_total,
        dim_sponsor.trials_completed,
        dim_sponsor.success_rate,
        min(fct_trials.start_date) as first_trial_date,
        extract(year from min(fct_trials.start_date))::int as cohort_year
    from "pharmapulse"."marts"."dim_sponsor" as dim_sponsor
    inner join "pharmapulse"."marts"."fct_trials" as fct_trials using (sponsor_key)
    where fct_trials.start_date is not null
    group by 1, 2, 3, 4, 5

),

cohort_summary as (

    select
        cohort_year,
        count(distinct sponsor_key) as cohort_sponsor_count,
        sum(trials_total) as cohort_total_trials,
        sum(trials_completed) as cohort_total_completed,
        round(avg(success_rate), 4) as cohort_avg_success_rate
    from sponsor_first_year
    group by cohort_year

),

sponsor_trial_activity_years as (

    select
        fct_trials.sponsor_key,
        fct_trials.nct_id,
        generate_series(
            extract(year from fct_trials.start_date)::int,
            coalesce(
                extract(year from fct_trials.completion_date)::int,
                extract(year from fct_trials.start_date)::int
            )
        ) as activity_year
    from "pharmapulse"."marts"."fct_trials" as fct_trials
    where fct_trials.start_date is not null
      and fct_trials.sponsor_key is not null

),

cohort_activity as (

    select
        sponsor_first_year.cohort_year,
        sponsor_trial_activity_years.activity_year,
        count(distinct sponsor_trial_activity_years.sponsor_key) as active_sponsor_count
    from sponsor_trial_activity_years
    inner join sponsor_first_year using (sponsor_key)
    where sponsor_trial_activity_years.activity_year >= sponsor_first_year.cohort_year
    group by 1, 2

),

final as (

    select
        
    md5(
        concat_ws('||',
            coalesce(cast(cohort_activity.cohort_year as varchar), ''), 
            coalesce(cast(cohort_activity.activity_year as varchar), '')
        )
    )
 as cohort_activity_key,
        cohort_activity.cohort_year,
        cohort_activity.activity_year,
        cohort_activity.activity_year - cohort_activity.cohort_year as years_since_cohort,
        cohort_activity.active_sponsor_count,
        first_value(cohort_activity.active_sponsor_count) over (
            partition by cohort_activity.cohort_year order by cohort_activity.activity_year
            rows between unbounded preceding and current row
        ) as cohort_launch_sponsor_count,
        round(
            cohort_activity.active_sponsor_count::numeric
            / nullif(
                first_value(cohort_activity.active_sponsor_count) over (
                    partition by cohort_activity.cohort_year order by cohort_activity.activity_year
                    rows between unbounded preceding and current row
                ),
                0
            ),
            4
        ) as survivorship_rate,
        cohort_summary.cohort_sponsor_count,
        cohort_summary.cohort_total_trials,
        cohort_summary.cohort_total_completed,
        cohort_summary.cohort_avg_success_rate
    from cohort_activity
    left join cohort_summary using (cohort_year)

)

select * from final