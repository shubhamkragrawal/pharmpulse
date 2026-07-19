with trial_conditions as (

    select * from "pharmapulse"."staging"."stg_trial_conditions"

),

conditions as (

    select * from "pharmapulse"."marts"."dim_condition"

),

final as (

    select
        
    md5(
        concat_ws('||',
            coalesce(cast(trial_conditions.nct_id as varchar), ''), 
            coalesce(cast(conditions.condition_key as varchar), '')
        )
    )
 as bridge_key,
        trial_conditions.nct_id,
        conditions.condition_key
    from trial_conditions
    inner join conditions using (condition_name)

)

select * from final