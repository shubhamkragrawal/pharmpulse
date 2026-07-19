-- GRAIN: one row per start_year. Sourced only from fct_trials date fields
-- (no bridge_trial_condition join, so no multi_condition_flag here). No phase
-- dimension -- see metric_duration_trends_by_phase.sql for the by-phase cut
-- (kept as a separate model so this one's grain/numbers, already quoted in
-- the M4 notebook and decisions.md, don't shift under a downstream milestone).

with trial_years as (

    select
        nct_id,
        duration_days,
        extract(year from start_date)::int as start_year
    from "pharmapulse"."marts"."fct_trials"
    where duration_days is not null
      and start_date is not null

),

yearly_median as (

    select
        start_year,
        count(*) as trial_count,
        (percentile_cont(0.25) within group (order by duration_days))::numeric as p25_duration_days,
        (percentile_cont(0.5) within group (order by duration_days))::numeric as median_duration_days,
        (percentile_cont(0.75) within group (order by duration_days))::numeric as p75_duration_days
    from trial_years
    group by start_year

),

final as (

    select
        start_year,
        trial_count,
        round(p25_duration_days, 1) as p25_duration_days,
        round(median_duration_days, 1) as median_duration_days,
        round(p75_duration_days, 1) as p75_duration_days,
        round(lag(median_duration_days) over (order by start_year), 1) as prior_year_median_duration_days,
        round(median_duration_days - lag(median_duration_days) over (order by start_year), 1) as yoy_change_days,
        round(
            (median_duration_days - lag(median_duration_days) over (order by start_year))
            / nullif(lag(median_duration_days) over (order by start_year), 0)
            * 100,
            2
        ) as yoy_change_pct
    from yearly_median

)

select * from final