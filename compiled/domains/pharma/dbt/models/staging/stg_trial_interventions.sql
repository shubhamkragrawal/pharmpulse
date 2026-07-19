with source as (

    select * from "pharmapulse"."raw"."ct_studies"

),

interventions as (

    select
        nct_id,
        nullif(trim(i.value ->> 'name'), '') as intervention_name,
        nullif(trim(i.value ->> 'type'), '') as intervention_type
    from source
    cross join lateral jsonb_array_elements(
        coalesce(payload -> 'protocolSection' -> 'armsInterventionsModule' -> 'interventions', '[]'::jsonb)
    ) as i(value)

),

final as (

    -- distinct enforces the (nct_id, intervention_name, intervention_type) grain
    -- even if CT.gov's source array ever repeats an entry for a single trial.
    select distinct
        nct_id,
        intervention_name,
        intervention_type
    from interventions
    where intervention_name is not null

)

select * from final