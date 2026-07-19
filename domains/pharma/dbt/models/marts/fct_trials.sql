with trials as (

    select * from {{ ref('stg_trials') }}

),

sponsors as (

    select * from {{ ref('dim_sponsor') }}

),

final as (

    select
        trials.nct_id,
        sponsors.sponsor_key,
        trials.phase,
        trials.overall_status,
        trials.enrollment_count,
        trials.start_date,
        trials.completion_date,
        trials.completion_date - trials.start_date as duration_days,
        trials.overall_status = 'TERMINATED' as is_terminated,
        trials.has_results,
        trials.num_primary_outcomes,
        trials.num_sites
    from trials
    left join sponsors on trials.sponsor_name = sponsors.sponsor_name

)

select * from final
