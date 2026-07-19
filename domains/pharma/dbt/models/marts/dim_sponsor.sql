with sponsors as (

    select * from {{ ref('stg_sponsors') }}

),

trial_counts as (

    select
        sponsor_name,
        count(*) as trials_total,
        count(*) filter (where overall_status = 'COMPLETED') as trials_completed
    from {{ ref('stg_trials') }}
    where sponsor_name is not null
    group by sponsor_name

),

final as (

    select
        {{ generate_surrogate_key(['sponsors.sponsor_name']) }} as sponsor_key,
        sponsors.sponsor_name,
        sponsors.sponsor_class,
        trial_counts.trials_total,
        trial_counts.trials_completed,
        -- inner join guarantees trials_total >= 1 (every stg_sponsors row is
        -- derived from stg_trials), so no divide-by-zero guard is needed here.
        round(trial_counts.trials_completed::numeric / trial_counts.trials_total, 4) as success_rate
    from sponsors
    inner join trial_counts using (sponsor_name)

)

select * from final
