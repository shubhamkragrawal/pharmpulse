with trial_conditions as (

    select * from {{ ref('stg_trial_conditions') }}

),

conditions as (

    select * from {{ ref('dim_condition') }}

),

final as (

    select
        {{ generate_surrogate_key(['trial_conditions.nct_id', 'conditions.condition_key']) }} as bridge_key,
        trial_conditions.nct_id,
        conditions.condition_key
    from trial_conditions
    inner join conditions using (condition_name)

)

select * from final
