with source as (

    select * from {{ source('raw', 'ct_studies') }}

),

conditions as (

    select
        nct_id,
        nullif(trim(c.value #>> '{}'), '') as condition_name
    from source
    cross join lateral jsonb_array_elements(
        coalesce(payload -> 'protocolSection' -> 'conditionsModule' -> 'conditions', '[]'::jsonb)
    ) as c(value)

),

final as (

    -- distinct enforces the (nct_id, condition_name) grain even if CT.gov's
    -- source array ever repeats an entry for a single trial.
    select distinct
        nct_id,
        condition_name
    from conditions
    where condition_name is not null

)

select * from final
