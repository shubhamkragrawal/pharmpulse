-- GRAIN: one row per (start_year, phase). Added in M5 for the Streamlit
-- duration-trends dashboard's by-phase cut. Kept separate from
-- metric_duration_trends.sql (which stays start_year-only) rather than adding
-- phase to that model's GROUP BY, so M4's already-documented numbers don't
-- shift under a later milestone. See decisions.md.
--
-- phase is fct_trials' raw pipe-delimited passthrough (e.g. "PHASE1|PHASE2"
-- for combined-phase trials) -- each distinct phase string is its own row
-- here, not split into constituent phases. Trials with a NULL phase
-- (observational studies, ~24%) are excluded from this model, not
-- reassigned to a fabricated "UNKNOWN" bucket.

with trial_years as (

    select
        nct_id,
        phase,
        duration_days,
        extract(year from start_date)::int as start_year
    from "pharmapulse"."marts"."fct_trials"
    where duration_days is not null
      and start_date is not null
      and phase is not null

),

yearly_median as (

    select
        start_year,
        phase,
        count(*) as trial_count,
        (percentile_cont(0.25) within group (order by duration_days))::numeric as p25_duration_days,
        (percentile_cont(0.5) within group (order by duration_days))::numeric as median_duration_days,
        (percentile_cont(0.75) within group (order by duration_days))::numeric as p75_duration_days
    from trial_years
    group by start_year, phase

),

final as (

    select
        
    md5(
        concat_ws('||',
            coalesce(cast(start_year as varchar), ''), 
            coalesce(cast(phase as varchar), '')
        )
    )
 as duration_by_phase_key,
        start_year,
        phase,
        trial_count,
        round(p25_duration_days, 1) as p25_duration_days,
        round(median_duration_days, 1) as median_duration_days,
        round(p75_duration_days, 1) as p75_duration_days,
        round(
            lag(median_duration_days) over (partition by phase order by start_year),
            1
        ) as prior_year_median_duration_days,
        round(
            median_duration_days - lag(median_duration_days) over (partition by phase order by start_year),
            1
        ) as yoy_change_days
    from yearly_median

)

select * from final