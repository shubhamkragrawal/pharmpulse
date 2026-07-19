with source as (

    select distinct intervention_name, intervention_type
    from "pharmapulse"."staging"."stg_trial_interventions"

),

final as (

    select
        
    md5(
        concat_ws('||',
            coalesce(cast(intervention_name as varchar), ''), 
            coalesce(cast(intervention_type as varchar), '')
        )
    )
 as intervention_key,
        intervention_name,
        intervention_type
    from source

)

select * from final