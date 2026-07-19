with trial_interventions as (

    select * from {{ ref('stg_trial_interventions') }}

),

interventions as (

    select * from {{ ref('dim_intervention') }}

),

final as (

    select
        {{ generate_surrogate_key(['trial_interventions.nct_id', 'interventions.intervention_key']) }} as bridge_key,
        trial_interventions.nct_id,
        interventions.intervention_key
    from trial_interventions
    inner join interventions using (intervention_name, intervention_type)

)

select * from final
