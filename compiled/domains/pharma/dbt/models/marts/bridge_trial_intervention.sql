with trial_interventions as (

    select * from "pharmapulse"."staging"."stg_trial_interventions"

),

interventions as (

    select * from "pharmapulse"."marts"."dim_intervention"

),

final as (

    select
        
    md5(
        concat_ws('||',
            coalesce(cast(trial_interventions.nct_id as varchar), ''), 
            coalesce(cast(interventions.intervention_key as varchar), '')
        )
    )
 as bridge_key,
        trial_interventions.nct_id,
        interventions.intervention_key
    from trial_interventions
    inner join interventions using (intervention_name, intervention_type)

)

select * from final