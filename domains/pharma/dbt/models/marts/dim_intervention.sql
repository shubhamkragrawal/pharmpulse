with source as (

    select distinct intervention_name, intervention_type
    from {{ ref('stg_trial_interventions') }}

),

final as (

    select
        {{ generate_surrogate_key(['intervention_name', 'intervention_type']) }} as intervention_key,
        intervention_name,
        intervention_type
    from source

)

select * from final
